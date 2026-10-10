let symbol="NIFTY";
let state={market:null,analysis:null};
let paper=JSON.parse(localStorage.getItem("oi_paper_v2")||"null")||{capital:100000,realized:0,open:null,trades:[]};

const $=id=>document.getElementById(id);
const fmt=x=>x==null||Number.isNaN(Number(x))?"--":Number(x).toLocaleString("en-IN",{maximumFractionDigits:2});
const money=x=>"₹"+Number(x||0).toLocaleString("en-IN",{maximumFractionDigits:2});

function setText(id,v){
  const el=$(id);
  if(el) el.textContent=v==null?"--":v;
}

function num(id){
  const v=Number($(id)?.value);
  return Number.isFinite(v)&&String($(id).value).trim()!==""?v:null;
}

function savePaper(){
  localStorage.setItem("oi_paper_v2",JSON.stringify(paper));
  renderPaper();
}

async function load(){
  $("status").textContent="LOADING "+symbol+"...";

  try{
    const r=await fetch("/api/analysis?symbol="+symbol,{cache:"no-store"});
    const j=await r.json();

    state.analysis=j;
    render(j);

    $("status").textContent=j.market?.ok
      ?"DATA FETCH COMPLETED"
      :"DATA SOURCE ERROR";

    checkAutoExit();

  }catch(e){
    console.error(e);
    $("status").textContent="CONNECTION ERROR";
  }
}

function render(j){
  const m=j.market||{};
  const i=j.indicators||{};
  const c=j.option_chain||{};
  const d=j.decision||{};

  setText("price",fmt(i.close));
  setText("marketSource",m.source||"--");
  setText("candleCount",(m.candles||[]).length);

  setText("ema9",fmt(i.ema9));
  setText("ema21",fmt(i.ema21));
  setText("vwap",fmt(i.vwap));
  setText("rsi",fmt(i.rsi));
  setText("atr",fmt(i.atr));
  setText("adx",fmt(i.adx));

  setText("volume",i.volume==null?"--":fmt(i.volume));

  setText(
    "volratio",
    i.volume_ratio==null?"--":fmt(i.volume_ratio)+"x"
  );

  setText("pcr",fmt(c.pcr));
  setText("ceoi",fmt(c.total_ce_oi));
  setText("peoi",fmt(c.total_pe_oi));
  setText("expiry",c.expiry||"--");

  setText(
    "oiSource",
    c.ok
      ?"NSE option chain"
      :"NSE unavailable: "+(c.error||"NSE may block cloud requests")
  );

  setText("condition",d.condition||"WAIT");
  setText("signal",d.signal||"WAIT");
  setText("confidence",(d.confidence||0)+"% confidence");

  setText("bull",d.bull_score??0);
  setText("bear",d.bear_score??0);

  setText("entry",fmt(d.entry));
  setText("sl",fmt(d.suggested_sl));
  setText("target",fmt(d.suggested_target));

  setText("reason",d.reason||"Waiting...");

  if(!$("manualEntry").value && i.close!=null){
    $("manualEntry").placeholder="Auto: "+fmt(i.close);
  }
}

function paperPrice(){
  return state.analysis?.indicators?.close??null;
}

function openPaper(type){

  if(paper.open){
    alert("Close the existing paper trade first.");
    return;
  }

  const current=paperPrice();

  const entry=num("manualEntry")??current;
  const trigger=num("manualTrigger");
  const sl=num("manualSL");
  const target=num("manualTarget");
  const units=num("manualUnits")??1;

  if(entry==null){
    alert(
      "Current index price is unavailable. Enter the entry price manually."
    );
    return;
  }

  if(trigger==null||sl==null||target==null){
    alert(
      "Enter a stop-loss trigger, stop-loss price, and target before opening a paper trade."
    );
    return;
  }

  if(units<=0){
    alert("Units / multiplier must be greater than zero.");
    return;
  }

  if(
    type==="CALL" &&
    !(target>entry && trigger<entry && sl<=trigger)
  ){
    alert(
      "For CALL: Target must be above entry; trigger below entry; stop-loss price at or below trigger."
    );
    return;
  }

  if(
    type==="PUT" &&
    !(target<entry && trigger>entry && sl>=trigger)
  ){
    alert(
      "For PUT: Target must be below entry; trigger above entry; stop-loss price at or above trigger."
    );
    return;
  }

  paper.open={
    type,
    entry,
    trigger,
    sl,
    target,
    units,
    time:new Date().toLocaleString("en-IN"),
    symbol,
    entrySource:num("manualEntry")!=null
      ?"MANUAL"
      :"CURRENT INDEX"
  };

  savePaper();
  checkAutoExit();
}

function closePaper(exitPrice=null,status="MANUAL CLOSE"){

  if(!paper.open) return;

  const price=exitPrice??paperPrice();

  if(price==null){
    alert(
      "Current index price is unavailable. Retry when data returns."
    );
    return;
  }

  const t=paper.open;
  const dir=t.type==="CALL"?1:-1;

  const pnl=(price-t.entry)*dir*t.units;

  paper.realized+=pnl;
  paper.capital+=pnl;

  paper.trades.unshift({
    time:t.time,
    type:t.type,
    symbol:t.symbol,
    entry:t.entry,
    trigger:t.trigger,
    sl:t.sl,
    target:t.target,
    exit:price,
    pnl,
    status
  });

  paper.open=null;
  savePaper();
}

function checkAutoExit(){

  if(!paper.open) return;

  const price=paperPrice();

  if(price==null) return;

  const t=paper.open;

  if(t.type==="CALL"){

    if(price>=t.target){
      closePaper(t.target,"TARGET HIT");
    }
    else if(price<=t.trigger){
      closePaper(t.sl,"STOP-LOSS TRIGGERED");
    }

  }else{

    if(price<=t.target){
      closePaper(t.target,"TARGET HIT");
    }
    else if(price>=t.trigger){
      closePaper(t.sl,"STOP-LOSS TRIGGERED");
    }
  }
}

function renderPaper(){

  setText("capital",money(paper.capital));
  setText("pnl",money(paper.realized));
  setText("tradeCount",paper.trades.length);

  setText(
    "openTrade",
    paper.open
      ?`${paper.open.symbol} ${paper.open.type} @ ${fmt(paper.open.entry)} | Trigger ${fmt(paper.open.trigger)} | SL ${fmt(paper.open.sl)} | Target ${fmt(paper.open.target)}`
      :"None"
  );

  const table=$("tradeRows");

  if(!table) return;

  table.innerHTML=paper.trades.map(t=>
    `<tr>
      <td>${t.time}</td>
      <td>${t.symbol||""} ${t.type}</td>
      <td>${fmt(t.entry)}</td>
      <td>${fmt(t.trigger)}</td>
      <td>${fmt(t.sl)}</td>
      <td>${fmt(t.target)}</td>
      <td>${fmt(t.exit)}</td>
      <td>${money(t.pnl)}</td>
      <td>${t.status}</td>
    </tr>`
  ).join("");
}

$("nifty").onclick=()=>{
  symbol="NIFTY";
  $("nifty").classList.add("active");
  $("bank").classList.remove("active");
  load();
};

$("bank").onclick=()=>{
  symbol="BANKNIFTY";
  $("bank").classList.add("active");
  $("nifty").classList.remove("active");
  load();
};

$("refresh").onclick=load;

$("callTrade").onclick=()=>openPaper("CALL");

$("putTrade").onclick=()=>openPaper("PUT");

$("closeTrade").onclick=()=>closePaper(null,"MANUAL CLOSE");

renderPaper();
load();

setInterval(load,30000);
