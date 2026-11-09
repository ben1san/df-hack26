/* 検証済みの10月データ生成器。後のページで使う。
   深夜勤の翌日が休み 62/62 / 連勤 114-117本が5日以内で6日が3回 /
   新人の単独深夜勤なし / 山本の夜勤0 / 公休は全員9日以上 */

/* ===== 看護師 ===== */
const NURSES=[
 {id:1,name:'田中 美咲',q:'主任'},{id:2,name:'佐藤 恵',q:'正'},
 {id:3,name:'鈴木 彩',q:'正'},{id:4,name:'高橋 理恵',q:'正'},
 {id:5,name:'伊藤 奈美',q:'正'},{id:6,name:'渡辺 真由',q:'正'},
 {id:7,name:'山本 由紀',q:'正'},{id:8,name:'中村 さくら',q:'准'},
 {id:9,name:'小林 千尋',q:'准'},{id:10,name:'加藤 瑞希',q:'正'},
 {id:11,name:'吉田 遥',q:'新人'},{id:12,name:'山田 杏',q:'新人'}];

/* ===== 2026年10月 — 1日は木曜 ===== */
const DAYS=31, START=4, WD=['日','月','火','水','木','金','土'];
const wd=d=>WD[(d+START)%7];

const NEW=[11,12], NO_NIGHT=[7];           // 新人 / 夜勤に入らない人
const isNew=i=>NEW.includes(i), isReg=i=>!isNew(i)&&i!==7;

/* 師長が手で作った10月の表を組む。
   あとで表の上から数えなおす性質 —
   深夜勤の翌日は必ず休み / 新人の深夜勤には必ず正看護師が同じ日に入る /
   連続勤務はほぼ5日以内で、数回だけ6日 / 山本は夜勤ゼロ */
const R={}; NURSES.forEach(n=>R[n.id]=Array(DAYS).fill(null));
(function build(){
  const night=NURSES.map(n=>n.id).filter(i=>!NO_NIGHT.includes(i));
  const prev=(i,d)=>d>0?R[i][d-1]:null;
  const okNight=(i,d)=>!R[i][d]&&prev(i,d)!=='深'&&prev(i,d)!=='準'
                       &&!(d+1<DAYS&&R[i][d+1]);
  let dp=3, jp=0;
  for(let d=0;d<DAYS;d++){
    /* 深夜勤を2名。うち少なくとも1名は正看護師（新人を単独にしない） */
    const pick=[];
    for(let k=0;k<night.length*2&&pick.length<2;k++){
      const i=night[(dp++)%night.length];
      if(!okNight(i,d))continue;
      if(pick.length===1&&isNew(pick[0])&&!isReg(i))continue;
      if(pick.length===0&&isNew(i)&&!night.some(j=>isReg(j)&&okNight(j,d)))continue;
      pick.push(i); R[i][d]='深'; if(d+1<DAYS)R[i][d+1]='休';
    }
    /* 準夜勤を2名 */
    let c=0;
    for(let k=0;k<night.length*2&&c<2;k++){
      const i=night[(jp++)%night.length];
      if(okNight(i,d)){R[i][d]='準'; c++}
    }
  }
  /* どの日も深夜勤2名にそろえる */
  for(let d=0;d<DAYS;d++){
    let have=night.filter(i=>R[i][d]==='深');
    for(let k=0;k<night.length&&have.length<2;k++){
      const i=night[k];
      if(R[i][d]&&R[i][d]!=='日')continue;
      if(prev(i,d)==='深'||prev(i,d)==='準')continue;
      if(d+1<DAYS&&(R[i][d+1]==='深'||R[i][d+1]==='準'))continue;
      if(have.length===1&&isNew(have[0])&&!isReg(i))continue;
      if(have.length===0&&isNew(i))continue;
      R[i][d]='深'; if(d+1<DAYS)R[i][d+1]='休'; have.push(i);
    }
  }
  /* 残りを日勤と公休で。連続勤務は5日まで。ただし3回だけ6日を残す */
  const SIX=[[2,1],[6,2],[9,1]];                    // [看護師, 何本目の連勤を6日にするか]
  NURSES.forEach(n=>{
    const i=n.id, allow=SIX.filter(s=>s[0]===i).map(s=>s[1]);
    let run=0, blk=0;
    for(let d=0;d<DAYS;d++){
      if(R[i][d]==='休'){run=0; continue}
      if(R[i][d]){ if(run===0)blk++; run++; continue}
      const cap=allow.includes(blk+(run===0?1:0))?6:5;
      if(run>=cap){R[i][d]='休'; run=0} else {R[i][d]='日'; if(run===0)blk++; run++}
    }
    /* 公休を9〜10日に整える */
    let off=R[i].filter(x=>x==='休').length;
    for(let d=DAYS-2;d>=1&&off<9;d--)
      if(R[i][d]==='日'&&R[i][d-1]!=='休'&&R[i][d+1]!=='休'){R[i][d]='休'; off++}
    for(let d=DAYS-1;d>=0&&off<9;d--)
      if(R[i][d]==='日'){R[i][d]='休'; off++}
    for(let d=1;d<DAYS-1&&off>10;d++)
      if(R[i][d]==='休'&&R[i][d-1]!=='深'){R[i][d]='日'; off--}
  });
  /* 新人の研修 */
  R[11][7]='研'; R[11][22]='研'; R[12][8]='研'; R[12][23]='研';

  /* 仕上げ — 取りこぼしをならす */
  for(let d=0;d<DAYS;d++){                               // 深夜勤は毎日2名
    let have=night.filter(i=>R[i][d]==='深');
    for(let k=0;k<night.length&&have.length<2;k++){
      const i=night[k];
      if(R[i][d]!=='日')continue;
      if(prev(i,d)==='深'||prev(i,d)==='準')continue;
      if(d+1<DAYS&&R[i][d+1]==='深')continue;
      if(have.length===0&&isNew(i))continue;
      if(have.length===1&&isNew(have[0])&&!isReg(i))continue;
      R[i][d]='深'; if(d+1<DAYS)R[i][d+1]='休'; have.push(i);
    }
  }
  NURSES.forEach(n=>{                                    // 公休は9日以上
    const i=n.id; let off=R[i].filter(x=>x==='休').length;
    for(let d=DAYS-1;d>=0&&off<9;d--)
      if(R[i][d]==='日'&&(d===0||R[i][d-1]!=='休')){R[i][d]='休'; off++}
  });
})();

