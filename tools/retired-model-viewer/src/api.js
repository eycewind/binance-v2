const base = (import.meta.env.VITE_API_URL?.trim() || "http://localhost:8000").replace(/\/+$/, "");
async function json(path, options) { const r=await fetch(`${base}${path}`,options); if(!r.ok){const b=await r.json().catch(()=>({}));throw new Error(b.detail||`API request failed (${r.status})`)} return r.json() }
export const fetchSymbols = options => json("/symbols",options);
export const fetchTrades = (filters,options) => { const q=new URLSearchParams(); Object.entries(filters).forEach(([k,v])=>{if(v!==""&&v!==false&&v!=null)q.set(k,v)}); return json(`/trades?${q}`,options) };
export const fetchOhlcv = (symbol,start,end,interval,options) => json(`/ohlcv/${encodeURIComponent(symbol)}?${new URLSearchParams({start,end,interval})}`,options);
