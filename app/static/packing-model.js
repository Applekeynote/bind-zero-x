'use strict';
// Pure geometry and operator-input policy; no image-derived material or force claims.
globalThis.BZXModel=(()=>{
  const finite=(value,min,max)=>Number.isFinite(Number(value))&&Number(value)>=min&&Number(value)<=max;
  function dimensions(piece){
    if(finite(piece.longMm,20,3000)&&finite(piece.shortMm,20,3000)&&finite(piece.thicknessMm,.5,50)&&Number(piece.longMm)>=Number(piece.shortMm))return {long:Number(piece.longMm),short:Number(piece.shortMm),thickness:Number(piece.thicknessMm),units:'mm'};
    const box=piece.bbox||[0,0,1,.7],axis=piece.shape_evidence?.image_long_axis_degrees||0;
    const width=box[2]*(piece.sourceWidth||960),height=box[3]*(piece.sourceHeight||720);
    const long=Math.max(piece.shape_evidence?.image_long_edge_px||Math.max(width,height),10),short=Math.max(10,piece.shape_evidence?.image_short_edge_px||Math.min(width,height));
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
    const result=[...pieces].sort((a,b)=>dim(b).long*dim(b).short-dim(a).long*dim(a).short||a.id-b.id);
    result.forEach((piece,index)=>{
      piece.orientation??=0;piece.foldEdge??=index%2?'toward you':'away from you';
      if(!index)return;
      const prev=result[index-1],pd=dim(prev),below={width:prev.orientation===90?pd.short:pd.long,depth:prev.orientation===90?pd.long:pd.short},d=dim(piece);
      const overlap=(w,h)=>Math.min(w,below.width)*Math.min(h,below.depth)/(w*h);
      piece.orientation=overlap(d.short,d.long)>overlap(d.long,d.short)?90:0;
    });return result;
  }
  function layout(pieces){
    const measured=pieces.length>0&&pieces.every(p=>dimensions(p).units==='mm');
    // Mixed physical and image units never enter a common layout.
    const footprints=pieces.map(p=>measured?footprint(p):footprint({...p,longMm:null,shortMm:null,thicknessMm:null}));
    const normalizer=Math.max(1,...footprints.flatMap(p=>[p.width,p.depth]));
    let height=0;
    const layers=pieces.map((piece,i)=>{const d=footprints[i],layer={id:piece.id,width:d.width/normalizer*3.2,depth:d.depth/normalizer*3.2,thickness:d.thickness/normalizer*3.2,y:height,orientation:piece.orientation||0};height+=layer.thickness;return layer;});
    return {layers,width:Math.max(.1,...layers.map(l=>l.width)),depth:Math.max(.1,...layers.map(l=>l.depth)),height,units:measured?'mm':'relative',normalizer};
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
  return {dimensions,knotPolicy,footprint,optimize,layout,route,halfKnot};
})();
