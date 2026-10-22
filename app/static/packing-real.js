import * as THREE from './vendor/three/three.module.js';

// Original photo-textured renderer. Image surfaces stay tied to their source masks.
const host=document.getElementById('packing-stage');
const model=globalThis.BZXModel;
const imageCache=new Map();
let renderer,scene,camera,group,lights,undersideLight,floor,resizeObserver,frame=0,generation=0;
let state=null,playing=true,phase=0,lastTime=0,speed=1,view='FRONT',yaw=.58,pitch=.75,distance=4.4,drag=null;
let assets=[],ropeMeshes=[],moving=null,currentLayout=null;
const v=p=>new THREE.Vector3(...p);
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const ease=t=>t*t*(3-2*t);

function image(url){
  if(!imageCache.has(url))imageCache.set(url,new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('Unable to load the source photo.'));img.src=url;}));
  if(imageCache.size>32)imageCache.delete(imageCache.keys().next().value);
  return imageCache.get(url);
}
function disposeObject(object){object.traverse(child=>{child.geometry?.dispose();for(const material of Array.isArray(child.material)?child.material:child.material?[child.material]:[]){material.map?.dispose();material.dispose();}});}
function resetGroup(){if(group){scene.remove(group);disposeObject(group);}group=new THREE.Group();scene.add(group);ropeMeshes=[];moving=null;}
function initialize(){
  if(renderer)return;
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.75));renderer.setClearColor('#ddd9cb');
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1;
  renderer.domElement.setAttribute('aria-label','Actual photo cutouts with 3D stacking and twine routing');
  renderer.domElement.setAttribute('role','img');renderer.domElement.tabIndex=0;
  scene=new THREE.Scene();scene.background=new THREE.Color('#ddd9cb');
  camera=new THREE.PerspectiveCamera(42,1,.01,100);
  scene.add(new THREE.HemisphereLight('#fffbed','#7b6d59',1.6));
  lights=new THREE.DirectionalLight('#fff7e8',2.1);lights.position.set(-3,7,4);lights.castShadow=true;
  lights.shadow.mapSize.set(1024,1024);lights.shadow.camera.left=-4;lights.shadow.camera.right=4;lights.shadow.camera.top=4;lights.shadow.camera.bottom=-4;lights.shadow.normalBias=.015;scene.add(lights);
  undersideLight=new THREE.DirectionalLight('#fffbed',2.2);undersideLight.position.set(2,-5,3);undersideLight.visible=false;scene.add(undersideLight);
  floor=new THREE.Mesh(new THREE.PlaneGeometry(30,30),new THREE.MeshStandardMaterial({color:'#c7c1b1',roughness:1}));floor.rotation.x=-Math.PI/2;floor.position.y=-.09;floor.receiveShadow=true;scene.add(floor);
  renderer.domElement.onpointerdown=e=>{drag=[e.clientX,e.clientY];renderer.domElement.setPointerCapture(e.pointerId);};
  renderer.domElement.onpointermove=e=>{if(!drag)return;yaw-=(e.clientX-drag[0])*.008;pitch=Math.max(-1.35,Math.min(1.5,pitch+(e.clientY-drag[1])*.008));view='ORBIT';drag=[e.clientX,e.clientY];updateCamera();};
  renderer.domElement.onpointerup=()=>drag=null;
  renderer.domElement.onwheel=e=>{if(!e.ctrlKey)return;e.preventDefault();distance=Math.max(1.3,Math.min(10,distance+e.deltaY*.004));updateCamera();};
  renderer.domElement.onkeydown=e=>{if(e.key==='ArrowLeft')yaw-=.12;else if(e.key==='ArrowRight')yaw+=.12;else if(e.key==='ArrowUp')pitch=Math.min(1.5,pitch+.12);else if(e.key==='ArrowDown')pitch=Math.max(-1.35,pitch-.12);else return;e.preventDefault();view='ORBIT';updateCamera();};
  resizeObserver=new ResizeObserver(resize);resizeObserver.observe(host);
  window.addEventListener('pagehide',()=>{cancelAnimationFrame(frame);renderer?.dispose();});
}
function resize(){if(!renderer)return;const width=Math.max(240,host.clientWidth),height=Math.max(320,Math.min(520,width*.66));renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();}
function updateCamera(){
  if(!camera||!state)return;
  const height=currentLayout?.height||.12;
  const knot=state.step.kind.startsWith('KNOT');
  const center=new THREE.Vector3(0,knot?height+.14:height/2,0),r=knot?distance*.28:distance;
  camera.position.set(center.x+r*Math.sin(yaw)*Math.cos(pitch),center.y+r*Math.sin(pitch),center.z+r*Math.cos(yaw)*Math.cos(pitch));
  camera.lookAt(center);floor.visible=pitch>0;undersideLight.visible=pitch<0;
}
function label(text,color='#26313a'){
  const canvas=document.createElement('canvas');canvas.width=384;canvas.height=96;
  const ctx=canvas.getContext('2d');ctx.fillStyle='rgba(250,249,240,.94)';ctx.fillRect(0,0,384,96);ctx.fillStyle=color;ctx.font='34px Pixel, monospace';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,192,50);
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
  const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false,toneMapped:false}));sprite.scale.set(1,.25,1);return sprite;
}
async function cutout(piece,input){
  const capture=piece.flatCapture,region=capture?.region||piece;
  const source=capture?.url||input.source,width=capture?.width||input.width,height=capture?.height||input.height;
  const photo=await image(source),canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(photo,0,0,width,height);
  const labels=capture?.labels_png||input.labels_png;
  if(labels&&region.shape_hypothesis!=='USER_SELECTED_REGION'){
    const map=await image(labels),maskCanvas=document.createElement('canvas');maskCanvas.width=width;maskCanvas.height=height;
    const maskCtx=maskCanvas.getContext('2d',{willReadFrequently:true});maskCtx.drawImage(map,0,0,width,height);
    const mask=maskCtx.getImageData(0,0,width,height).data,data=ctx.getImageData(0,0,width,height);
    for(let i=0;i<data.data.length;i+=4)data.data[i+3]=mask[i]===region.id?255:0;
    ctx.putImageData(data,0,0);
  }else{
    ctx.globalCompositeOperation='destination-in';ctx.beginPath();region.polygon.forEach(([x,y],i)=>i?ctx.lineTo(x*width,y*height):ctx.moveTo(x*width,y*height));ctx.closePath();ctx.fill();
  }
  return {canvas,region,width,height};
}
function surface(piece,asset,layer){
  const {region,width,height,canvas}=asset;
  const angle=(region.shape_evidence?.image_long_axis_degrees||0)*Math.PI/180;
  const c=Math.cos(angle),s=Math.sin(angle),polygon=region.polygon;
  let points=polygon.map(([x,y])=>{const px=x*width,py=y*height;return {x:px*c+py*s,y:-px*s+py*c};});
  const minX=Math.min(...points.map(p=>p.x)),maxX=Math.max(...points.map(p=>p.x)),minY=Math.min(...points.map(p=>p.y)),maxY=Math.max(...points.map(p=>p.y));
  const long=piece.orientation===90?layer.depth:layer.width,short=piece.orientation===90?layer.width:layer.depth;
  const sx=long/Math.max(1,maxX-minX),sy=short/Math.max(1,maxY-minY),cx=(minX+maxX)/2,cy=(minY+maxY)/2;
  const shape=new THREE.Shape();points.forEach((p,i)=>{const x=(p.x-cx)*sx,y=-(p.y-cy)*sy;i?shape.lineTo(x,y):shape.moveTo(x,y);});shape.closePath();
  for(const hole of region.holes||[]){
    const path=new THREE.Path();hole.forEach(([x,y],i)=>{const px=x*width,py=y*height,hx=(px*c+py*s-cx)*sx,hy=-(-px*s+py*c-cy)*sy;i?path.lineTo(hx,hy):path.moveTo(hx,hy);});path.closePath();shape.holes.push(path);
  }
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=Math.min(4,renderer.capabilities.getMaxAnisotropy());
  const geometry=new THREE.ShapeGeometry(shape),positions=geometry.attributes.position,uv=geometry.attributes.uv;
  for(let i=0;i<positions.count;i++){
    const px=positions.getX(i)/sx+cx,py=-positions.getY(i)/sy+cy;
    const originalX=px*c-py*s,originalY=px*s+py*c;
    uv.setXY(i,originalX/width,1-originalY/height);
  }
  uv.needsUpdate=true;
  const top=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({map:texture,roughness:.97,metalness:0,alphaTest:.4,side:THREE.DoubleSide}));
  top.position.z=layer.thickness+.0003;
  const side=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:layer.thickness,bevelEnabled:false,steps:1}),new THREE.MeshStandardMaterial({color:'#ad8c5d',roughness:1}));
  const g=new THREE.Group();g.add(side,top);g.rotation.x=-Math.PI/2;
  const wrapper=new THREE.Group();wrapper.add(g);wrapper.rotation.y=-(piece.orientation||0)*Math.PI/180;wrapper.position.y=layer.y;wrapper.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});
  // The measured thickness is extruded; no unseen back photograph is fabricated.
  return wrapper;
}
function tube(points,color,radius=.014,closed=false){
  const curve=new THREE.CatmullRomCurve3(points.map(v),closed,'centripetal',.1);
  const geometry=new THREE.TubeGeometry(curve,Math.min(256,Math.max(96,points.length*12)),radius,8,closed);
  const fiber=document.createElement('canvas');fiber.width=256;fiber.height=64;const ctx=fiber.getContext('2d');ctx.fillStyle='#fff6df';ctx.fillRect(0,0,256,64);
  for(let i=-64;i<320;i+=8){ctx.strokeStyle=i%16?'#baad8d':'#e8dcba';ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(i,0);ctx.lineTo(i+30,64);ctx.stroke();}
  const texture=new THREE.CanvasTexture(fiber);texture.colorSpace=THREE.SRGBColorSpace;texture.wrapS=THREE.RepeatWrapping;texture.wrapT=THREE.RepeatWrapping;texture.repeat.set(14,1);
  const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,map:texture,roughness:.87,metalness:0}));mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);
  return {mesh,curve,count:geometry.index.count};
}
function roundedRoute(points){
  // Small corner neighborhoods stop a smooth curve cutting through the bundle.
  const result=[points[0]];
  for(let i=1;i<points.length-1;i++){
    const prev=v(points[i-1]),p=v(points[i]),next=v(points[i+1]);
    const fraction=.04;result.push(p.clone().lerp(prev,fraction).toArray(),points[i],p.clone().lerp(next,fraction).toArray());
  }result.push(points.at(-1));return result;
}
function knotStrands(kind,policy,height){
  const y=height+.10,complete=kind==='KNOT_SECOND';
  const firstHalf=model.halfKnot(policy.firstTurns||1,1,y,-.13);
  const a=[[.7,y+.09,-.35],...firstHalf.a],b=[[-.7,y+.09,-.35],...firstHalf.b];
  if(complete){
    const reverseHalf=model.halfKnot(1,-1,y,.13);
    // Keep the completed first half; each SAME strand returns through the
    // opposite second crossing. Separate depth lanes show over/under contact.
    a.push([-.44,y+.02,0],...reverseHalf.b,[.7,y+.09,.35]);
    b.push([.44,y+.02,0],...reverseHalf.a,[-.7,y+.09,.35]);
  }else{a.push([-.7,y+.09,.35]);b.push([.7,y+.09,.35]);}
  const first=tube(a,'#c88b39',.018),second=tube(b,'#457c95',.018);
  ropeMeshes.push(first,second);
}
function renderPhotoFold(input){
  cancelAnimationFrame(frame);
  if(renderer)renderer.domElement.remove();
  host.replaceChildren();host.classList.add('photo-fold-stage');
  const wrapper=document.createElement('div');wrapper.className='real-fold-photo';
  const capture=input.step.piece.flatCapture;
  const img=document.createElement('img');img.src=capture?.url||input.source;img.alt=capture?'Actual flattened capture':'Actual source photo: open and flatten the selected box';wrapper.append(img);
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 1 1');svg.setAttribute('preserveAspectRatio','none');
  const polygon=document.createElementNS(svg.namespaceURI,'polygon');polygon.setAttribute('points',(capture?.region||input.step.piece).polygon.map(p=>p.join(',')).join(' '));polygon.setAttribute('fill','none');polygon.setAttribute('stroke',input.step.piece.color);polygon.setAttribute('stroke-width','.008');svg.append(polygon);wrapper.append(svg);host.append(wrapper);
  host.dataset.renderer='SOURCE_PHOTO_FOLD';
}
async function show(input){
  const ticket=++generation;state=input;playing=!input.paused;phase=input.paused?1:0;lastTime=0;
  document.getElementById('packing-end-key').hidden=!input.step.kind.startsWith('KNOT');
  if(input.step.kind==='FOLD'){renderPhotoFold(input);return;}
  try{
    initialize();host.classList.remove('photo-fold-stage');
    host.replaceChildren(renderer.domElement);host.dataset.renderer='PHOTO_TEXTURED_WEBGL';
    resetGroup();currentLayout=model.layout(input.pieces);const layout=currentLayout;
    const visible=input.step.kind==='PLACE'?input.pieces.slice(0,input.pieces.findIndex(p=>p.id===input.step.piece.id)+1):input.pieces;
    assets=await Promise.all(visible.map(p=>cutout(p,input)));if(ticket!==generation)return;
    for(let i=0;i<visible.length;i++){
      const p=visible[i];if(p.review==='OPEN'&&!p.flatCapture)continue;
      const g=surface(p,assets[i],layout.layers[i]);group.add(g);
      if(input.step.kind==='PLACE'&&p.id===input.step.piece.id){const tag=label('REGION '+String(p.id).padStart(2,'0'));tag.position.set(-layout.layers[i].width/2-.18,layout.layers[i].y+.28,.1);group.add(tag);}
      if(input.step.kind==='PLACE'&&p.id===input.step.piece.id)moving={object:g,y:layout.layers[i].y,rotation:g.rotation.y};
    }
    const policy=model.knotPolicy(input.condition);
    const ropeKinds=['WRAP_LONG','WRAP_CROSS','KNOT_FIRST','KNOT_SECOND','CHECK'];
    if(ropeKinds.includes(input.step.kind)){
      const long=tube(roundedRoute(model.route(layout,'LONG')),'#e9dcc0');
      if(input.step.kind==='WRAP_LONG')ropeMeshes.push(long);
    }
    if(['WRAP_CROSS','KNOT_FIRST','KNOT_SECOND','CHECK'].includes(input.step.kind)){
      const cross=tube(roundedRoute(model.route(layout,'CROSS')),'#dfd0ad');
      if(input.step.kind==='WRAP_CROSS')ropeMeshes.push(cross);
    }
    if(input.step.kind.startsWith('KNOT'))knotStrands(input.step.kind,policy,layout.height);
    if(input.step.kind==='CHECK')knotStrands('KNOT_SECOND',policy,layout.height);
    const front=label('FRONT / YOU');front.position.set(0,-.015,layout.depth/2+.4);group.add(front);
    host.dataset.units=layout.units;host.dataset.visiblePieces=String(visible.length);
    host.dataset.knot=policy.id;
    document.getElementById('packing-scale-label').textContent=layout.units==='mm'?'MEASURED / mm':'PHOTO PROPORTIONS';
    resize();updateCamera();cancelAnimationFrame(frame);frame=requestAnimationFrame(tick);
  }catch(error){
    if(ticket!==generation)return;
    host.replaceChildren();const img=document.createElement('img');img.src=input.source;img.alt='Actual photo for this step';host.append(img);host.dataset.renderer='SOURCE_PHOTO_FALLBACK';
    const message=document.createElement('span');message.className='real-render-status';message.textContent='Photo view · 3D is unavailable on this device';host.append(message);
    console.error('Packing renderer:',error.message);
  }
}
function tick(time){
  if(!renderer||!state||state.step.kind==='FOLD')return;
  if(host.offsetParent===null||document.hidden){lastTime=0;frame=requestAnimationFrame(tick);return;}
  if(lastTime&&time-lastTime<32){frame=requestAnimationFrame(tick);return;}
  const delta=lastTime?Math.min(.05,(time-lastTime)/1000):0;lastTime=time;
  if(playing&&!reduced)phase=(phase+delta*speed/6)%1;
  if(playing)document.getElementById('packing-scrub').value=Math.round(phase*100);
  const t=reduced?1:ease(Math.min(1,phase/.72));
  if(moving){moving.object.position.y=moving.y+(1-t)*1.3;moving.object.position.x=(1-t)*-.7;moving.object.rotation.y=moving.rotation+(1-t)*.45;}
  for(const rope of ropeMeshes){const count=Math.max(3,Math.floor(rope.count*(playing?t:Math.max(t,.02))/3)*3);rope.mesh.geometry.setDrawRange(0,reduced?rope.count:count);}
  renderer.render(scene,camera);frame=requestAnimationFrame(tick);
}
function setView(value){
  view=value;
  if(value==='TOP'){yaw=0;pitch=1.5;distance=4.4;}
  else if(value==='UNDER'){yaw=.5;pitch=-.7;distance=4.4;}
  else if(value==='SIDE'){yaw=Math.PI/2;pitch=.18;distance=4.4;}
  else{yaw=.58;pitch=.75;distance=4.4;}
  updateCamera();
}
document.getElementById('packing-camera-views').onclick=e=>{const b=e.target.closest('[data-real-view]');if(b){setView(b.dataset.realView);document.querySelectorAll('[data-real-view]').forEach(button=>button.setAttribute('aria-pressed',String(button===b)));}};
document.getElementById('packing-speed').onchange=e=>speed=Number(e.target.value);
document.getElementById('packing-scrub').oninput=e=>{phase=Number(e.target.value)/100;playing=false;document.dispatchEvent(new Event('real-guide-paused'));};
globalThis.bzxRealGuide={show,pause:value=>playing=!value,replay:()=>{phase=0;},setView,hide:()=>{generation++;state=null;cancelAnimationFrame(frame);if(scene)resetGroup();}};
document.dispatchEvent(new Event('real-guide-ready'));
