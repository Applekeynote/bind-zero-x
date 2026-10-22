// Run with node --test tests/auth_flow.test.cjs. All credentials are fixtures.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../app/static/auth.js'),'utf8');
const state = csrf => ({authenticated:false,configured:true,csrf});
const reply = (body,status=200) => ({status,ok:status>=200&&status<300,json:async()=>body});

async function screen(responses,pathname='/') {
  const elements = new Map(), calls = [], redirects = [];
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector,{value:'',hidden:true,disabled:false,focus(){}});
    return elements.get(selector);
  }
  const fetch = async (url,options={}) => {
    calls.push({url,...options});
    assert.ok(responses.length,'unexpected network call');
    return responses.shift();
  };
  vm.runInNewContext(source,{document:{querySelector:element},fetch,location:{pathname,replace:url=>redirects.push(url)}});
  await new Promise(setImmediate);
  element('#auth-password').value='fixture-only-password-1234';
  element('#auth-code').value='123456';
  return {calls,redirects,element,submit:()=>element('#auth-form').onsubmit({preventDefault(){}})};
}

test('an idle login refreshes its challenge before submitting credentials',async()=>{
  const h=await screen([reply(state('expired')),reply(state('fresh')),reply({authenticated:true})]);
  await h.submit();
  assert.deepEqual(h.calls.map(c=>c.url),['/auth/session','/auth/session','/auth/login']);
  assert.equal(h.calls[2].headers['X-CSRF-Token'],'fresh');
  assert.deepEqual(h.redirects,['/']);
  assert.equal(h.element('#auth-password').value,'');
});

test('a rotated challenge is recovered once without another OTP entry',async()=>{
  const h=await screen([reply(state('old')),reply(state('first')),reply({detail:'INVALID_CSRF'},403),reply(state('rotated')),reply({authenticated:true})]);
  await h.submit();
  const posts=h.calls.filter(c=>c.method==='POST');
  assert.equal(posts.length,2);
  assert.equal(posts[1].headers['X-CSRF-Token'],'rotated');
  assert.equal(posts[0].body,posts[1].body);
  assert.deepEqual(h.redirects,['/']);
});

test('wrong factors are never automatically resubmitted',async()=>{
  const h=await screen([reply(state('old')),reply(state('fresh')),reply({detail:'INVALID_CREDENTIALS'},401)]);
  await h.submit();
  assert.equal(h.calls.filter(c=>c.method==='POST').length,1);
  assert.equal(h.redirects.length,0);
  assert.match(h.element('#auth-error').textContent,/password/);
});

test('retry is bounded and a sign-in error never claims setup expired',async()=>{
  const h=await screen([reply(state('old')),reply(state('first')),reply({detail:'INVALID_CSRF'},403),reply(state('second')),reply({detail:'INVALID_CSRF'},403)]);
  await h.submit();
  assert.equal(h.calls.filter(c=>c.method==='POST').length,2);
  assert.match(h.element('#auth-error').textContent,/sign-in session changed/);
  assert.equal(h.element('#auth-submit').disabled,false);
});

test('a login completed in another tab redirects without submitting factors',async()=>{
  const h=await screen([reply(state('old')),reply({authenticated:true,configured:true,csrf:'signed-in'})]);
  await h.submit();
  assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
  assert.deepEqual(h.redirects,['/']);
});

test('expired enrollment is not silently restarted with a different secret',async()=>{
  const h=await screen([reply({authenticated:false,configured:false,setup_allowed:true,csrf:'setup'}),reply({secret:'FIXTURE',qr:'data:fixture'}),reply({detail:'INVALID_CSRF'},403)]);
  await h.submit();
  h.element('#auth-code').value='123456';
  await h.submit();
  assert.deepEqual(h.calls.map(c=>c.url),['/auth/session','/auth/setup/begin','/auth/setup/finish']);
  assert.match(h.element('#auth-error').textContent,/setup session expired/);
});

test('judge login submits its own username without an OTP',async()=>{
 const h=await screen([reply(state('first')),reply(state('fresh')),reply({authenticated:true})]);
 h.element('#auth-username').value='judge';await h.submit();
 const payload=JSON.parse(h.calls.find(c=>c.method==='POST').body);
 assert.equal(payload.username,'judge');assert.equal(payload.code,undefined);
});

test('dedicated judge page asks only for its password',async()=>{
 const h=await screen([reply(state('first')),reply(state('fresh')),reply({authenticated:true})],'/judge');
 assert.equal(h.element('#username-field').hidden,true);
 assert.equal(h.element('#code-field').hidden,true);
 assert.equal(h.element('#auth-code').required,false);
 await h.submit();
 const payload=JSON.parse(h.calls.find(c=>c.method==='POST').body);
 assert.equal(payload.username,'judge');assert.equal(payload.code,undefined);
 assert.deepEqual(h.redirects,['/']);
});
