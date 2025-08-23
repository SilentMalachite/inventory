(() => {
  const { useState, useEffect } = React;

  function api(path, opts={}){
    return fetch(path, Object.assign({headers:{'Accept-Language':'ja','Content-Type':'application/json'}}, opts)).then(r=>r.json());
  }

  function Dashboard(){
    const [items, setItems] = useState([]);
    const [balances, setBalances] = useState({});
    const [form, setForm] = useState({sku:'', name:'', category:'', unit:'pcs', min_stock:0});
    const [move, setMove] = useState({item_id:'', qty:1, ref:''});
    const [msg, setMsg] = useState('');

    const load = async () => {
      const [its, bals] = await Promise.all([
        api('/items/'),
        fetch('/stock/balances').then(r=>r.json())
      ]);
      setItems(its); setBalances(bals);
    };
    useEffect(()=>{load();},[]);

    const submitItem = async (e)=>{
      e.preventDefault();
      const res = await api('/items/', {method:'POST', body: JSON.stringify(form)});
      if(res && res.id){ setMsg('商品を登録しました'); setForm({sku:'', name:'', category:'', unit:'pcs', min_stock:0}); load(); }
      else if(res && res.detail){ setMsg(res.detail); }
    };

    const doMove = async (kind)=>{
      if(!move.item_id) return;
      const body = { item_id: Number(move.item_id), qty: Number(move.qty), ref: move.ref||null };
      const path = kind==='IN'? '/stock/in' : kind==='OUT'? '/stock/out' : '/stock/adjust';
      const r = await api(path, {method:'POST', body: JSON.stringify(body)});
      if(r && r.id){ setMsg(kind==='IN'?'入庫を登録しました': kind==='OUT'?'出庫を登録しました':'在庫調整を登録しました'); setMove({...move, qty:1, ref:''}); load(); }
      else if(r && r.detail){ setMsg(r.detail); }
    };

    return (
      React.createElement('div', null,
        React.createElement('div', {className:'toolbar'},
          React.createElement('a', {href:'/'}, 'SSR画面へ'),
          React.createElement('span', null, msg)
        ),
        React.createElement('div', {className:'row'},
          React.createElement('div', {className:'card'},
            React.createElement('h2', null, '在庫状況'),
            React.createElement('table', null,
              React.createElement('thead', null, React.createElement('tr', null,
                React.createElement('th', null, 'ID'),
                React.createElement('th', null, 'SKU'),
                React.createElement('th', null, '商品名'),
                React.createElement('th', null, '現在庫'),
                React.createElement('th', null, '最低在庫'),
                React.createElement('th', null, '単位')
              )),
              React.createElement('tbody', null,
                items.map(it => React.createElement('tr', {key:it.id, className: (balances[it.id]??0) < (it.min_stock||0)?'low':''},
                  React.createElement('td', null, it.id),
                  React.createElement('td', null, it.sku),
                  React.createElement('td', null, it.name),
                  React.createElement('td', {className:'num'}, (balances[it.id]??0)),
                  React.createElement('td', {className:'num'}, it.min_stock),
                  React.createElement('td', null, it.unit)
                ))
              )
            )
          ),
          React.createElement('div', {className:'card'},
            React.createElement('h2', null, '商品登録'),
            React.createElement('form', {onSubmit: submitItem},
              React.createElement('div', {className:'grid'},
                React.createElement('label', null, 'SKU', React.createElement('input', {value:form.sku, onChange:e=>setForm({...form, sku:e.target.value})})),
                React.createElement('label', null, '商品名', React.createElement('input', {value:form.name, onChange:e=>setForm({...form, name:e.target.value})})),
                React.createElement('label', null, 'カテゴリ', React.createElement('input', {value:form.category, onChange:e=>setForm({...form, category:e.target.value})})),
                React.createElement('label', null, '単位', React.createElement('input', {value:form.unit, onChange:e=>setForm({...form, unit:e.target.value})})),
                React.createElement('label', null, '最低在庫', React.createElement('input', {type:'number', value:form.min_stock, onChange:e=>setForm({...form, min_stock:e.target.value})}))
              ),
              React.createElement('div', {className:'actions'}, React.createElement('button', {type:'submit'}, '登録'))
            )
          ),
          React.createElement('div', {className:'card'},
            React.createElement('h2', null, '入出庫 / 調整'),
            React.createElement('div', {className:'grid'},
              React.createElement('label', null, '商品',
                React.createElement('select', {value:move.item_id, onChange:e=>setMove({...move, item_id:e.target.value})},
                  React.createElement('option', {value:''}, '選択してください'),
                  items.map(it=>React.createElement('option', {key:it.id, value:it.id}, `${it.id} | ${it.sku} | ${it.name}`))
                )
              ),
              React.createElement('label', null, '数量', React.createElement('input', {type:'number', value:move.qty, onChange:e=>setMove({...move, qty:e.target.value})})),
              React.createElement('label', null, '参照', React.createElement('input', {value:move.ref, onChange:e=>setMove({...move, ref:e.target.value})}))
            ),
            React.createElement('div', {className:'actions'},
              React.createElement('button', {onClick:()=>doMove('IN')}, '入庫'), ' ',
              React.createElement('button', {onClick:()=>doMove('OUT')}, '出庫'), ' ',
              React.createElement('button', {onClick:()=>doMove('ADJUST')}, '在庫調整')
            )
          )
        )
      )
    );
  }

  const root = ReactDOM.createRoot(document.getElementById('app'));
  root.render(React.createElement(Dashboard));
})();

