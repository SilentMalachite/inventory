import React from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

function App(){
  return <Dashboard/>
}

function useApi(){
  const api = async (path: string, opts: RequestInit = {}) => {
    const res = await fetch(path, {
      headers: { 'Accept-Language': 'ja', 'Content-Type': 'application/json' },
      ...opts,
    })
    const ct = res.headers.get('content-type') || ''
    if (ct.includes('application/json')) return await res.json()
    return await res.text()
  }
  return { api }
}

type Item = { id:number; sku:string; name:string; unit:string; min_stock:number; category?:string }

function Dashboard(){
  const { api } = useApi()
  type Enriched = Item & { balance?: number, low?: boolean }
  const [items, setItems] = React.useState<Enriched[]>([])
  const [balances, setBalances] = React.useState<Record<number, number>>({})
  const [q, setQ] = React.useState('')
  const [lowOnly, setLowOnly] = React.useState(false)
  const [category, setCategory] = React.useState('')
  const [minBalance, setMinBalance] = React.useState<string>('')
  const [maxBalance, setMaxBalance] = React.useState<string>('')
  const [categories, setCategories] = React.useState<string[]>([])
  const [page, setPage] = React.useState(1)
  const [size, setSize] = React.useState(20)
  const [total, setTotal] = React.useState(0)
  const [sortBy, setSortBy] = React.useState<string>('id')
  const [sortDir, setSortDir] = React.useState<string>('asc')
  const [trendId, setTrendId] = React.useState<number|''>('')
  const [trend, setTrend] = React.useState<{date:string,balance:number}[]|null>(null)
  const [msg, setMsg] = React.useState<string>('')
  const [form, setForm] = React.useState({ sku:'', name:'', category:'', unit:'pcs', min_stock:0 })
  const [move, setMove] = React.useState({ item_id:'', qty:1, ref:'' })
  const [edit, setEdit] = React.useState<Enriched|null>(null)

  const load = async ()=>{
    const params = new URLSearchParams()
    if(q) params.set('q', q)
    if(category) params.set('category', category)
    if(lowOnly) params.set('low_only', 'true')
    if(minBalance) params.set('min_balance', String(minBalance))
    if(maxBalance) params.set('max_balance', String(maxBalance))
    params.set('page', String(page))
    params.set('size', String(size))
    params.set('sort_by', sortBy)
    params.set('sort_dir', sortDir)
    const res = await api('/stock/search' + (params.toString()?`?${params.toString()}`:'')) as any
    const enriched: Enriched[] = res.items || []
    setItems(enriched)
    setTotal(res.total || 0)
    const m: Record<number, number> = {}
    for (const it of enriched) m[it.id] = it.balance ?? 0
    setBalances(m)
  }
  React.useEffect(()=>{ load() },[])
  React.useEffect(()=>{ (async()=>{
    const cats: string[] = await api('/items/categories')
    setCategories(cats)
  })() },[])
  React.useEffect(()=>{ load() },[page, size, sortBy, sortDir])

  const submitItem:React.FormEventHandler<HTMLFormElement> = async (e)=>{
    e.preventDefault()
    const r = await api('/items/', { method:'POST', body: JSON.stringify(form) })
    if((r as any).id){ setMsg('商品を登録しました'); setForm({ sku:'', name:'', category:'', unit:'pcs', min_stock:0 }); load() }
    else if((r as any).detail){ setMsg((r as any).detail) }
  }
  const doMove = async (kind:'IN'|'OUT'|'ADJUST')=>{
    if(!move.item_id) return
    const body = { item_id:Number(move.item_id), qty:Number(move.qty), ref: move.ref||null }
    const path = kind==='IN'? '/stock/in': kind==='OUT'? '/stock/out':'/stock/adjust'
    const r = await api(path, { method:'POST', body: JSON.stringify(body) })
    if((r as any).id){ setMsg(kind==='IN'?'入庫を登録しました': kind==='OUT'?'出庫を登録しました':'在庫調整を登録しました'); setMove({...move, qty:1, ref:''}); load() }
    else if((r as any).detail){ setMsg((r as any).detail) }
  }

  return (
    <div className="app">
      <header><h1>在庫ダッシュボード（SPA）</h1><a href="/">SSR</a></header>
      <main>
        <div className="row">
          <div className="card">
            <h2>在庫状況</h2>
            <div className="toolbar" style={{display:'flex', gap:8, marginBottom:8}}>
              <input placeholder="キーワード（SKU/商品名/カテゴリ）" value={q} onChange={e=>setQ(e.target.value)} />
              <label style={{display:'flex',alignItems:'center',gap:6}}>
                <input type="checkbox" checked={lowOnly} onChange={e=>setLowOnly(e.target.checked)} /> 低在庫のみ
              </label>
              <select value={category} onChange={e=>setCategory(e.target.value)}>
                <option value="">全カテゴリ</option>
                {categories.map(c=> <option key={c} value={c}>{c}</option>)}
              </select>
              <input placeholder="在庫最小" type="number" value={minBalance} onChange={e=>setMinBalance(e.target.value)} style={{width:110}} />
              <input placeholder="在庫最大" type="number" value={maxBalance} onChange={e=>setMaxBalance(e.target.value)} style={{width:110}} />
              <button onClick={()=>{ setPage(1); load() }}>検索</button>
              <span style={{marginLeft:8, opacity:.8}}>並び替え: {sortBy} / {sortDir}</span>
              <button onClick={()=>{ setSortBy('id'); setSortDir('asc'); setPage(1); }}>並び替えリセット</button>
              <button onClick={()=>{ setQ(''); setCategory(''); setLowOnly(false); setMinBalance(''); setMaxBalance(''); setPage(1); setSortBy('id'); setSortDir('asc'); load(); }}>条件リセット</button>
            </div>
            <table>
              <thead><tr>
                {([['id','ID'],['sku','SKU'],['name','商品名'],['balance','現在庫'],['min_stock','最低在庫'],['category','カテゴリ'],['unit','単位']] as [string,string][])
                  .map(([k,label])=> (
                  <th key={k} onClick={()=>{
                      // Toggle secondary sort: shift+click to add
                      setPage(1)
                      setSortBy(prev=>{
                        if((window as any).event?.shiftKey){
                          const list = prev.split(',').filter(Boolean)
                          // toggle presence or move to end
                          const i = list.indexOf(k)
                          if(i>=0){ list.splice(i,1); list.push(k) } else { list.push(k) }
                          return list.join(',')
                        }
                        return k
                      })
                      setSortDir(prev=>{
                        const parts = prev.split(',').filter(Boolean)
                        const dir = (sortBy.split(',')[0]===k && parts[0]==='asc')?'desc':'asc'
                        return (window as any).event?.shiftKey ? (parts.concat([dir]).join(',')) : dir
                      })
                  }} style={{cursor:'pointer'}}>
                    {label}{sortBy.split(',')[0]===k? (sortDir.split(',')[0]==='asc'?' ▲':' ▼'):''}
                  </th>
                ))}
              </tr></thead>
              <tbody>
                {items.map(it => (
                  <tr key={it.id} className={((it.balance ?? (balances[it.id]??0)) < (it.min_stock||0))?'low':''}>
                    <td>{it.id}</td>
                    <td>{it.sku}</td>
                    <td>{it.name}</td>
                    <td className="num">{it.balance ?? (balances[it.id]??0)}</td>
                    <td className="num">{it.min_stock}</td>
                    <td>{it.category||''}</td>
                    <td>{it.unit}</td>
                    <td><button onClick={()=>setEdit(it)}>編集</button> <button onClick={()=>setTrendId(it.id)}>推移</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {edit && (
              <div style={{marginTop:8, padding:12, border:'1px solid #2a2f45', borderRadius:8}}>
                <h3>編集: {edit.sku}</h3>
                <div className="grid">
                  <label>商品名<input value={edit.name} onChange={e=>setEdit({...edit!, name:e.target.value})}/></label>
                  <label>カテゴリ<input value={edit.category||''} onChange={e=>setEdit({...edit!, category:e.target.value})}/></label>
                  <label>単位<input value={edit.unit} onChange={e=>setEdit({...edit!, unit:e.target.value})}/></label>
                  <label>最低在庫<input type="number" value={edit.min_stock} onChange={e=>setEdit({...edit!, min_stock:Number(e.target.value)})}/></label>
                </div>
                <div className="actions">
                  <button onClick={async()=>{ await api(`/items/${edit.id}`, {method:'PUT', body: JSON.stringify({ name: edit.name, category: edit.category||null, unit: edit.unit, min_stock: edit.min_stock })}); setEdit(null); load(); }}>保存</button>
                  <button onClick={()=>setEdit(null)} style={{marginLeft:8}}>キャンセル</button>
                </div>
              </div>
            )}
            <div style={{display:'flex',alignItems:'center',gap:8,marginTop:8}}>
              <button disabled={page<=1} onClick={()=>setPage(p=>Math.max(1,p-1))}>前へ</button>
              <span>ページ <input style={{width:60}} type="number" min={1} max={Math.max(1, Math.ceil(total/size))} value={page} onChange={e=>setPage(Math.max(1, Number(e.target.value||1)))} /> / {Math.max(1, Math.ceil(total/size))}（全{total}件）</span>
              <button disabled={page>=Math.ceil(total/size)} onClick={()=>setPage(p=>p+1)}>次へ</button>
              <select value={size} onChange={e=>{ setSize(Number(e.target.value)); setPage(1) }}>
                {[10,20,50,100].map(n=> <option key={n} value={n}>{n}件/頁</option>)}
              </select>
            </div>
          </div>
          <div className="card">
            <h2>CSVエクスポート</h2>
            <div className="grid">
              <label>エンコード
                <select id="enc">
                  <option value="utf-8-sig">UTF-8 (BOM付・推奨)</option>
                  <option value="cp932">Shift_JIS (CP932)</option>
                </select>
              </label>
            </div>
            <div className="actions">
              <a href="#" onClick={(e)=>{ e.preventDefault(); const enc=(document.getElementById('enc') as HTMLSelectElement).value; window.location.href = `/items/export/csv?encoding=${enc}` }}>ダウンロード</a>
            </div>
          </div>
          <div className="card">
            <h2>商品登録</h2>
            <form onSubmit={submitItem}>
              <div className="grid">
                <label>SKU<input value={form.sku} onChange={e=>setForm({...form, sku:e.target.value})} required/></label>
                <label>商品名<input value={form.name} onChange={e=>setForm({...form, name:e.target.value})} required/></label>
                <label>カテゴリ<input value={form.category} onChange={e=>setForm({...form, category:e.target.value})}/></label>
                <label>単位<input value={form.unit} onChange={e=>setForm({...form, unit:e.target.value})}/></label>
                <label>最低在庫<input type="number" value={form.min_stock} onChange={e=>setForm({...form, min_stock:Number(e.target.value)})}/></label>
              </div>
              <div className="actions"><button type="submit">登録</button><span style={{marginLeft:8}}>{msg}</span></div>
            </form>
          </div>
          <div className="card">
            <h2>カテゴリ一括操作</h2>
            <div className="grid">
              <label>対象カテゴリ
                <select id="catFrom" defaultValue="">
                  <option value="">選択してください</option>
                  {categories.map(c=> <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
              <label>変更後の名前<input id="catTo" placeholder="新しいカテゴリ名"/></label>
            </div>
            <div className="actions">
              <button onClick={async()=>{
                const from = (document.getElementById('catFrom') as HTMLSelectElement).value
                const to = (document.getElementById('catTo') as HTMLInputElement).value
                if(!from || !to) return
                await api('/items/categories/rename', {method:'POST', body: JSON.stringify({from, to})})
                const cats: string[] = await api('/items/categories'); setCategories(cats); load()
              }}>一括変更</button>
              <button style={{marginLeft:8}} onClick={async()=>{
                const from = (document.getElementById('catFrom') as HTMLSelectElement).value
                if(!from) return
                await api('/items/categories/delete', {method:'POST', body: JSON.stringify({category: from})})
                const cats: string[] = await api('/items/categories'); setCategories(cats); load()
              }}>一括削除</button>
            </div>
          </div>
          <div className="card">
            <h2>入出庫 / 調整</h2>
            <div className="grid">
              <label>商品
                <select value={move.item_id} onChange={e=>setMove({...move, item_id:e.target.value})}>
                  <option value="">選択してください</option>
                  {items.map(it=> <option key={it.id} value={it.id}>{`${it.id} | ${it.sku} | ${it.name}`}</option>)}
                </select>
              </label>
              <label>数量<input type="number" value={move.qty} onChange={e=>setMove({...move, qty:Number(e.target.value)})}/></label>
              <label>参照<input value={move.ref} onChange={e=>setMove({...move, ref:e.target.value})}/></label>
            </div>
            <div className="actions">
              <button onClick={()=>doMove('IN')}>入庫</button>
              <button onClick={()=>doMove('OUT')} style={{marginLeft:8}}>出庫</button>
              <button onClick={()=>doMove('ADJUST')} style={{marginLeft:8}}>在庫調整</button>
            </div>
          </div>
          <div className="card">
            <h2>在庫推移</h2>
            <div className="grid">
              <label>商品
                <select value={trendId} onChange={e=>{ const v = e.target.value? Number(e.target.value):''; setTrendId(v) }}>
                  <option value="">選択してください</option>
                  {items.map(it=> <option key={it.id} value={it.id}>{`${it.id} | ${it.sku} | ${it.name}`}</option>)}
                </select>
              </label>
              <label>日数<input id="trendDays" type="number" defaultValue={30} min={1} max={365}/></label>
              <button onClick={async()=>{ if(!trendId) return; const days = Number((document.getElementById('trendDays') as HTMLInputElement).value||30); const res = await api(`/stock/trend/${trendId}?days=${days}`); setTrend(res.series || []); }}>表示</button>
            </div>
            <TrendChart data={trend||[]} />
          </div>
        </div>
      </main>
    </div>
  )
}

function TrendChart({data}:{data:{date:string,balance:number}[]}){
  if(!data || data.length===0) return <div>データがありません</div>
  const w = 520, h = 220, pad = 36
  const xs = data.map(d=> new Date(d.date).getTime())
  const ys = data.map(d=> d.balance)
  const deltas = (data as any).map((d:any)=> d.delta ?? 0)
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minY = Math.min(...ys), maxY = Math.max(...ys)
  const sx = (x:number)=> pad + (w-2*pad) * ( (x-minX) / (maxX-minX||1) )
  const sy = (y:number)=> h-pad - (h-2*pad) * ( (y-minY) / (maxY-minY||1) )
  // Moving average (7日)
  const window = 7
  const ma:number[] = ys.map((_,i)=>{
    const s = Math.max(0, i-window+1)
    const arr = ys.slice(s,i+1)
    return Math.round( (arr.reduce((a,b)=>a+b,0) / arr.length) * 100 )/100
  })
  const path = xs.map((x,i)=> `${i?'L':'M'}${sx(x)},${sy(ys[i])}`).join(' ')
  const pathMA = xs.map((x,i)=> `${i?'L':'M'}${sx(x)},${sy(ma[i])}`).join(' ')
  const zeroY = sy(0)
  const [tip, setTip] = React.useState<{x:number,y:number,text:string}|null>(null)
  return (
    <svg width={w} height={h} style={{background:'#0f1424',borderRadius:8,border:'1px solid #2a2f45'}}
      onMouseMove={(e)=>{
        const rect = (e.target as SVGElement).closest('svg')!.getBoundingClientRect()
        const mx = e.clientX - rect.left
        // find nearest index by x
        let idx = 0, best = 1e12
        xs.forEach((x,i)=>{ const dx = Math.abs(sx(x)-mx); if(dx<best){ best=dx; idx=i } })
        setTip({x:sx(xs[idx]), y: sy(ys[idx]), text: `${new Date(xs[idx]).toLocaleDateString()}\n残高:${ys[idx]} 変化:${deltas[idx]}`})
      }}
      onMouseLeave={()=>setTip(null)}
    >
      {/* delta bars */}
      {xs.map((x,i)=>{
        const val = deltas[i]
        const y0 = zeroY
        const y1 = sy(ys[i]- (i>0? ys[i-1]: ys[i]-val)) // compute bar height per delta
        const top = Math.min(y0, y1), height = Math.abs(y1 - y0)
        const color = val>=0? '#2ecc71' : '#e74c3c'
        return <rect key={i} x={sx(x)-2} y={top} width={4} height={height} fill={color} opacity={0.7}/>
      })}
      {/* lines */}
      <path d={path} fill="none" stroke="#4cc2ff" strokeWidth={2}/>
      <path d={pathMA} fill="none" stroke="#ffd166" strokeWidth={2} strokeDasharray="4 3"/>
      {/* axis labels */}
      <text x={pad} y={16} fill="#aab4c8">{new Date(minX).toLocaleDateString()}</text>
      <text x={w-pad-80} y={16} fill="#aab4c8">{new Date(maxX).toLocaleDateString()}</text>
      <text x={pad} y={h-8} fill="#aab4c8">{minY}</text>
      <text x={w-pad-40} y={h-8} fill="#aab4c8">{maxY}</text>
      {/* tooltip */}
      {tip && (<g>
        <circle cx={tip.x} cy={tip.y} r={3} fill="#fff"/>
        <rect x={tip.x+8} y={tip.y-28} width={140} height={32} fill="#000" opacity={0.6} rx={4}/>
        <text x={tip.x+12} y={tip.y-16} fill="#fff" fontSize={10}>{tip.text.split('\n')[0]}</text>
        <text x={tip.x+12} y={tip.y-4} fill="#fff" fontSize={10}>{tip.text.split('\n')[1]}</text>
      </g>)}
    </svg>
  )
}

createRoot(document.getElementById('root')!).render(<App/>)
