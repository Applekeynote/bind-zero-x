'use strict';
// Pure geometry and operator-input policy; no image-derived material or force claims.
globalThis.BZXModel=(()=>{
  const finite=(value,min,max)=>Number.isFinite(Number(value))&&Number(value)>=min&&Number(value)<=max;
  function dimensions(piece){
    if(finite(piece.longMm,20,3000)&&finite(piece.shortMm,20,3000)&&finite(piece.thicknessMm,.5,50)&&Number(piece.longMm)>=Number(piece.shortMm))return {long:Number(piece.longMm),short:Number(piece.shortMm),thickness:Number(piece.thicknessMm),units:'mm'};
    const box=piece.bbox||[0,0,1,.7],axis=piece.shape_evidence?.image_long_axis_degrees||0;
    const width=box[2]*(piece.sourceWidth||960),height=box[3]*(piece.sourceHeight||720);
    const completed=piece.flatCapture?.region?.completion||piece.completion;
    const panel=piece.geometryMode!=='FULL_OUTLINE'&&completed;
    const long=Math.max((panel?completed.body_long_px:piece.shape_evidence?.image_long_edge_px)||Math.max(width,height),10),short=Math.max(10,(panel?completed.body_short_px:piece.shape_evidence?.image_short_edge_px)||Math.min(width,height));
    return {long,short,thickness:Math.max(2,long*.008),units:'relative',imageAxis:axis};
  }
  function knotPolicy(condition={}){
    const material=condition.material||'PAPER',springback=condition.springback||'LOW';
    if(!['PAPER','COTTON','SLICK'].includes(material)||!['LOW','HIGH'].includes(springback))throw Error('INVALID_BINDING_CONDITION');
    if(material==='SLICK')return {id:'CHANGE_TWINE',name:'Use grippy paper or cotton twine',ready:false,reason:'Smooth plastic line can slip. Change the binding material before following this bundle guide.'};
    return springback==='HIGH'?{id:'SURGEON',name:'Surgeon binding knot',ready:true,firstTurns:2,reason:'The stack springs back: two turns in the first crossing help hold the wrap while the reverse crossing is tied.'}:{id:'REEF',name:'Square binding knot',ready:true,firstTurns:1,reason:'Flat, low-springback sheets with grippy twine: use two opposite half-knots on top of the crossed wraps.'};
  }
  function footprint(piece){const d=dimensions(piece);return {width:piece.orientation===90?d.short:d.long,depth:piece.orientation===90?d.long:d.short,...d};}
  function optimize(pieces){
    const measured=pieces.length>0&&pieces.every(p=>dimensions(p).units==='mm');
    const dim=p=>dimensions(measured?p:{...p,longMm:null,shortMm:null,thicknessMm:null});
    const result=[...pieces].sort((a,b)=>dim(b).long*dim(b).short-dim(a).long*dim(a).short||(b.pixel_area||0)-(a.pixel_area||0)||a.id-b.id);
    const direction=result[0]?.orientation||0;
    result.forEach((piece,index)=>{piece.orientation=direction;piece.foldEdge=index%2?'toward you':'away from you';});
    // A broad cap presses the small inner sheets against the broad base.
    return result.length>2?[result[0],...result.slice(2),result[1]]:result;
  }
  function layout(pieces){
    const measured=pieces.length>0&&pieces.every(p=>dimensions(p).units==='mm');
    // Mixed physical and image units never enter a common layout.
    const footprints=pieces.map(p=>measured?footprint(p):footprint({...p,longMm:null,shortMm:null,thicknessMm:null}));
    const normalizer=Math.max(1,...footprints.flatMap(p=>[p.width,p.depth]));
    let height=0;
    const layers=pieces.map((piece,i)=>{const d=footprints[i],layer={id:piece.id,width:d.width/normalizer*3.2,depth:d.depth/normalizer*3.2,thickness:d.thickness/normalizer*3.2,y:height,orientation:piece.orientation||0};height+=layer.thickness;return layer;});
    const result={layers,width:Math.max(.1,...layers.map(l=>l.width)),depth:Math.max(.1,...layers.map(l=>l.depth)),height,units:measured?'mm':'relative',normalizer};
    result.support=assess(result);return result;
  }
  function assess(l){
    const layers=l.layers;if(!layers.length)return {ready:false,reason:'Select a piece.',lifting_verified:false};
    const base=layers[0],cap=layers.at(-1),inside=layers.slice(1,-1);
    const covered=(p,q)=>Math.min(p.width,q.width)*Math.min(p.depth,q.depth)/(p.width*p.depth);
    const ratios=inside.flatMap(p=>[covered(p,base),covered(p,cap)]);
    if(layers.length>1)ratios.push(covered(cap,base));
    const coverage=Math.min(1,...ratios),slenderness=l.height/Math.max(.001,Math.min(base.width,base.depth));
    const ready=coverage>=.98&&slenderness<=.25;
    return {ready,minimum_cover:coverage,height_to_short_edge:slenderness,centered:true,twine_crosses_every_panel:true,
      reason:coverage<.98?'Split this bundle or fold the projecting edges inside both cover sheets.':slenderness>.25?'Split this tall bundle into smaller bundles.':'Base and cap cover the centered inner panels.',
      lifting_verified:false,physical_friction_verified:false};
  }
  function plan(pieces){
    const measured=pieces.length>0&&pieces.every(p=>dimensions(p).units==='mm');
    const dim=p=>dimensions(measured?p:{...p,longMm:null,shortMm:null,thicknessMm:null});
    let pending=[...pieces].sort((a,b)=>dim(b).long*dim(b).short-dim(a).long*dim(a).short||(b.pixel_area||0)-(a.pixel_area||0)||a.id-b.id);const bundles=[];
    while(pending.length){
      const base=pending.shift(),d=dim(base),fit=p=>dim(p).long<=d.long*1.005&&dim(p).short<=d.short*1.005;
      const eligible=pending.filter(fit),cap=eligible[0];
      const members=cap?eligible.filter(p=>p===cap||(dim(p).long<=dim(cap).long*1.005&&dim(p).short<=dim(cap).short*1.005)):[];
      let chosen=[base],height=dim(base).thickness;
      for(const p of members){if(height+dim(p).thickness>Math.min(d.long,d.short)*.25)continue;chosen.push(p);height+=dim(p).thickness;}
      const ids=new Set(chosen.map(p=>p.id));pending=pending.filter(p=>!ids.has(p.id));
      const ordered=optimize(chosen);bundles.push({pieces:ordered,layout:layout(ordered)});
    }return {bundles,method:'CENTERED_BASE_CAP_PANEL_CONTAINMENT',units:measured?'mm':'relative',lifting_verified:false};
  }
  function route(layout,kind){
    const h=layout.height+.045,w=layout.width/2+.035,d=layout.depth/2+.035,b=-.035;
    if(kind==='LONG')return [[0,h,0],[0,h,-d],[0,b,-d],[0,b,d],[0,h,d],[0,h,0]];
    return [[0,h+.025,0],[-w,h+.025,0],[-w,b,0],[w,b,0],[w,h+.025,0],[0,h+.025,0]];
  }
  function halfKnot(turns,reverse,height,z){
    const a=[],b=[],span=.32,r=.043;
    for(let i=0;i<=80;i++){
      const t=i/80,x=span-2*span*t,phase=t*Math.PI*2*turns*reverse;
      a.push([x,height+Math.sin(phase)*r,z+Math.cos(phase)*r]);
      b.push([-x,height+Math.sin(-phase+Math.PI)*r,z+Math.cos(-phase+Math.PI)*r]);
    }return {a,b};
  }
  function bindingPaths(l,kind,turns=1){
    const y=l.height+.055,w=l.width/2+.025,d=l.depth/2+.025,b=-.045,mid=[0,b,0];
    let a=[mid,[0,b,d],[0,y,d],[0,y,.14]],bpath=[mid,[0,b,-d],[0,y,-d],[0,y,-.16]];
    if(kind!=='WRAP_LONG')a.push([-.24,y,.14],[-w,y,.14],[-w,b+.035,.14],[w,b+.035,.14],[w,y,.14],[.5,y+.035,-.13]);
    else a.push([.5,y+.035,-.13]);
    bpath.push([-.5,y+.035,-.13]);
    const first=halfKnot(turns,1,y+.08,-.13),firstA=first.a[0],firstB=first.b[0];
    a.push(firstA);bpath.push(firstB);
    const knotStartA=a.length-1,knotStartB=bpath.length-1;
    if(['KNOT_FIRST','KNOT_SECOND','CHECK'].includes(kind)){
      a.push(...first.a.slice(1));bpath.push(...first.b.slice(1));
      if(['KNOT_SECOND','CHECK'].includes(kind)){
        const second=halfKnot(1,-1,y+.08,.13);
        a.push([-.44,y+.10,0],...second.b,[.65,y+.13,.32]);
        bpath.push([.44,y+.10,0],...second.a,[-.65,y+.13,.32]);
      }else{a.push([-.65,y+.13,.32]);bpath.push([.65,y+.13,.32]);}
    }
    return {a,b:bpath,knotStartA,knotStartB,midpoint:mid,continuous:[...a].reverse().concat(bpath.slice(1)),kind};
  }
  return {dimensions,knotPolicy,footprint,optimize,plan,assess,layout,route,halfKnot,bindingPaths};
})();
