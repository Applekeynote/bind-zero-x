'use strict';
const form = document.querySelector('#auth-form');
let authState, setupStage = 0;
const error = document.querySelector('#auth-error');
const button = document.querySelector('#auth-submit');
function showError(message) { error.textContent = message; error.hidden = false; }
async function initialize() {
  try {
    const response = await fetch('/auth/session', {cache:'no-store'});
    if (!response.ok) throw new Error('Unable to connect.');
    authState = await response.json();
    if (authState.authenticated) return location.replace('/');
    if (!authState.configured) {
      if (!authState.setup_allowed) { form.hidden = true; document.querySelector('#auth-intro').textContent = 'Complete MFA setup on the desktop first.'; return; }
      setupStage = 1;
      document.querySelector('#auth-title').textContent = 'Set up MFA';
      document.querySelector('#auth-intro').textContent = 'Choose a password with 14–128 characters, then link your authenticator app.';
      document.querySelector('#auth-password').autocomplete = 'new-password';
      document.querySelector('#code-field').hidden = true;
      document.querySelector('#auth-code').required = false;
      button.textContent = 'Link authenticator →';
    }
  } catch (exception) { showError(exception.message); button.disabled = true; }
}
form.onsubmit = async event => {
  event.preventDefault(); error.hidden = true; button.disabled = true;
  try {
    const password = document.querySelector('#auth-password').value;
    const code = document.querySelector('#auth-code').value;
    const path = setupStage === 1 ? '/auth/setup/begin' : setupStage === 2 ? '/auth/setup/finish' : '/auth/login';
    const body = setupStage === 1 ? {password} : setupStage === 2 ? {code} : {password,code};
    const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':authState.csrf},body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) {
      const messages = {INVALID_CREDENTIALS:setupStage === 2 ? 'Enter the current six-digit code from the account you just scanned. Enable automatic date and time on both devices.' : 'Check your password and use a new authenticator code. Each code can be used once.',TRY_AGAIN_LATER:'Too many attempts. Try again in 15 minutes.',LOGIN_BUSY:'Sign-in is busy. Try again shortly.',INVALID_CSRF:'Your setup session expired. Reload this page and start again.',MFA_ALREADY_CONFIGURED:'MFA is already configured. Reload to sign in.',LOCAL_INITIAL_SETUP_ONLY:'Setup is already complete or unavailable here. Reload to sign in.'};
      throw new Error(messages[result.detail] || 'Unable to sign in. Check your details and try again.');
    }
    document.querySelector('#auth-password').value = '';
    if (setupStage === 1) {
      setupStage = 2;
      document.querySelector('#password-field').hidden = true;
      document.querySelector('#auth-password').required = false;
      document.querySelector('#auth-qr').src = result.qr;
      document.querySelector('#auth-secret').value = result.secret;
      document.querySelector('#enrollment').hidden = false;
      document.querySelector('#code-field').hidden = false;
      document.querySelector('#auth-code').required = true;
      document.querySelector('#auth-intro').textContent = 'Scan the QR with your authenticator app, then enter its six-digit code.';
      button.textContent = 'Activate MFA →'; document.querySelector('#auth-code').focus();
    } else location.replace('/');
  } catch (exception) { showError(exception.message); }
  finally { button.disabled = false; }
};
initialize();
