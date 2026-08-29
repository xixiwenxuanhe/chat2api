import { StrictMode, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Activity, AlertTriangle, Boxes, CheckCircle2, ChevronRight, Database,
  Eye, EyeOff, KeyRound, LayoutDashboard, LoaderCircle, LogOut, Menu,
  Plus, RefreshCw, Search, Server, ShieldCheck, Trash2, Waypoints, X,
} from 'lucide-react'
import { SiOpenapiinitiative } from 'react-icons/si'
import { RiBrainAi3Line } from 'react-icons/ri'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './styles.css'

const views = {
  overview: { label: '概览', description: '网关与账号池运行状态', icon: LayoutDashboard },
  credentials: { label: '凭据', description: '管理 ChatGPT 账号凭据', icon: KeyRound },
  models: { label: '模型', description: '查看官网实时模型目录', icon: Boxes },
  playground: { label: '游乐场', description: '在网关中直接测试模型', icon: Waypoints },
}

async function request(path, options = {}) {
  const response = await fetch(`/admin/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  const data = await response.json().catch(() => ({}))
  if (response.status === 401) throw new Error('UNAUTHORIZED')
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求失败')
  return data
}

const formatTime = value => value ? new Date(value * 1000).toLocaleString('zh-CN', { hour12: false }) : '—'

function Brand({ compact = false }) {
  return (
    <div className={`brand ${compact ? 'brand-compact' : ''}`}>
      <span className="brand-logo"><SiOpenapiinitiative aria-hidden="true" /></span>
      <span><strong>Chat2API</strong>{!compact && <small>Gateway Console</small>}</span>
    </div>
  )
}

function Login({ onLogin }) {
  const [key, setKey] = useState('')
  const [visible, setVisible] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault(); setLoading(true); setError('')
    try {
      await request('/login', { method: 'POST', body: JSON.stringify({ key }) })
      setKey(''); await onLogin()
    } catch (reason) {
      setError(reason.message === 'UNAUTHORIZED' ? '管理密钥不正确' : reason.message)
    } finally { setLoading(false) }
  }

  return (
    <main className="login-page">
      <div className="login-brand"><Brand /></div>
      <section className="login-panel">
        <div className="login-symbol"><ShieldCheck size={24} /></div>
        <div className="login-copy"><h1>欢迎回来</h1><p>登录以管理凭据与上游模型。</p></div>
        <form onSubmit={submit}>
          <label htmlFor="admin-key">管理密钥</label>
          <div className="password-field">
            <KeyRound size={17} />
            <input id="admin-key" type={visible ? 'text' : 'password'} value={key} onChange={e => setKey(e.target.value)} autoComplete="current-password" placeholder="请输入管理密钥" autoFocus required />
            <button type="button" className="icon-button" onClick={() => setVisible(!visible)} title={visible ? '隐藏密钥' : '显示密钥'}>{visible ? <EyeOff size={17} /> : <Eye size={17} />}</button>
          </div>
          {error && <div className="form-error"><AlertTriangle size={15} />{error}</div>}
          <button className="button button-primary login-button" disabled={loading}>{loading ? <LoaderCircle className="spin" size={17} /> : <LogOut size={17} />}登录</button>
        </form>
        <div className="login-note"><ShieldCheck size={14} />使用 HttpOnly Cookie 保护管理会话</div>
      </section>
      <footer>Chat2API · OpenAI-compatible gateway</footer>
    </main>
  )
}

function Sidebar({ view, setView, open, close, logout }) {
  return <>
    {open && <button className="scrim" onClick={close} aria-label="关闭导航" />}
    <aside className={open ? 'sidebar sidebar-open' : 'sidebar'}>
      <div className="sidebar-head"><Brand /><button className="icon-button sidebar-close" onClick={close} title="关闭"><X size={19} /></button></div>
      <div className="nav-label">工作区</div>
      <nav>{Object.entries(views).map(([id, item]) => { const Icon = item.icon; return <button key={id} className={view === id ? 'nav-item active' : 'nav-item'} onClick={() => { setView(id); close() }}><Icon size={18} /><span>{item.label}</span><ChevronRight size={15} /></button> })}</nav>
      <div className="sidebar-status"><span className="pulse" /><div><strong>服务在线</strong><small>Gateway connected</small></div></div>
      <button className="nav-item logout" onClick={logout}><LogOut size={18} /><span>退出登录</span></button>
    </aside>
  </>
}

function PageHeader({ view, openMenu }) {
  const item = views[view]
  return <header className="topbar"><div className="topbar-title"><button className="icon-button mobile-menu" onClick={openMenu} title="打开导航"><Menu size={20} /></button><div><h1>{item.label}</h1><p>{item.description}</p></div></div><div className="topbar-state"><span className="pulse" />运行中</div></header>
}

function Stat({ icon: Icon, label, value, tone }) {
  return <div className="stat"><span className={`stat-icon ${tone || ''}`}><Icon size={19} /></span><div><span>{label}</span><strong>{value ?? '—'}</strong></div></div>
}

function Overview({ status, modelCount, refresh, loading }) {
  return <div className="view-content">
    <div className="view-heading"><div><h2>运行概览</h2><p>账号池、代理与上游模型的当前状态</p></div><button className="button button-secondary" onClick={refresh} disabled={loading}><RefreshCw className={loading ? 'spin' : ''} size={16} />刷新</button></div>
    <div className="stats-grid">
      <Stat icon={Database} label="凭据总数" value={status?.credentials} />
      <Stat icon={CheckCircle2} label="可用凭据" value={status?.active_credentials} tone="success" />
      <Stat icon={AlertTriangle} label="异常凭据" value={status?.error_credentials} tone="warning" />
      <Stat icon={Boxes} label="可用模型" value={modelCount} tone="violet" />
    </div>
    <section className="surface"><div className="surface-head"><div><h3>服务配置</h3><p>当前网关运行模式</p></div><Activity size={19} /></div><div className="config-list">
      <div><span className="config-icon"><Server size={18} /></span><p><small>兼容协议</small><strong>OpenAI Chat Completions</strong></p><span className="badge">可用</span></div>
      <div><span className="config-icon"><Waypoints size={18} /></span><p><small>上游代理</small><strong>{status?.proxy_configured ? '已配置代理出口' : '直接连接'}</strong></p><span className={`badge ${status?.proxy_configured ? '' : 'neutral'}`}>{status?.proxy_configured ? '已启用' : '未启用'}</span></div>
      <div><span className="config-icon"><ShieldCheck size={18} /></span><p><small>Web 镜像</small><strong>仅运行 API 网关与管理端</strong></p><span className="badge neutral">已关闭</span></div>
    </div></section>
  </div>
}

function Credentials({ credentials, refresh, statusRefresh, notify }) {
  const [open, setOpen] = useState(false); const [content, setContent] = useState(''); const [busy, setBusy] = useState(false)
  async function add() { if (!content.trim()) return; setBusy(true); try { const result = await request('/credentials', { method: 'POST', body: JSON.stringify({ content }) }); setContent(''); setOpen(false); notify(result.created ? '凭据已添加' : '凭据已更新'); await Promise.all([refresh(), statusRefresh()]) } catch (e) { notify(e.message, true) } finally { setBusy(false) } }
  async function remove(id) { if (!confirm('确定删除该凭据？')) return; await request(`/credentials/${id}`, { method: 'DELETE' }); notify('凭据已删除'); await Promise.all([refresh(), statusRefresh()]) }
  async function refreshCredential(id) { try { await request(`/credentials/${id}/refresh`, { method: 'POST' }); notify('凭据已更新'); await Promise.all([refresh(), statusRefresh()]) } catch (e) { notify(e.message, true); await Promise.all([refresh(), statusRefresh()]) } }
  async function viewCredential(id) { try { const result = await request(`/credentials/${id}`); setDetail(result.session) } catch (e) { notify(e.message, true) } }
  async function clearErrors() { await request('/errors', { method: 'DELETE' }); notify('异常标记已清除'); await Promise.all([refresh(), statusRefresh()]) }
  const [detail, setDetail] = useState(null)
  return <div className="view-content"><div className="view-heading"><div><h2>凭据管理</h2><p>完整 Session 存储在受限权限数据卷</p></div><div className="actions"><button className="button button-secondary" onClick={clearErrors}><CheckCircle2 size={16} />清除异常</button><button className="button button-primary" onClick={() => setOpen(true)}><Plus size={16} />添加凭据</button></div></div>
    <section className="surface table-surface"><div className="table-meta"><span>{credentials.length} 个凭据</span><span>完整 Session 存储在受限权限数据卷</span></div>{credentials.length ? <div className="table-scroll"><table><thead><tr><th>账号</th><th>Account ID</th><th>AccessToken 到期</th><th>状态</th><th>更新时间</th><th aria-label="操作" /></tr></thead><tbody>{credentials.map(item => <tr key={item.id}><td><strong>{item.email || '未知邮箱'}</strong><small>{item.id}</small></td><td><code>{item.account_id}</code></td><td>{formatTime(item.access_expires_at)}</td><td><span className={`status-badge ${item.status}`}><span />{item.status === 'error' ? '异常' : '可用'}</span>{item.last_error && <small>{item.last_error}</small>}</td><td>{formatTime(item.updated_at)}</td><td><div className="row-actions"><button className="icon-button" onClick={() => viewCredential(item.id)} title="查看完整 JSON"><Eye size={17} /></button><button className="icon-button" onClick={() => refreshCredential(item.id)} title="更新凭据"><RefreshCw size={17} /></button><button className="icon-button danger" onClick={() => remove(item.id)} title="删除凭据"><Trash2 size={17} /></button></div></td></tr>)}</tbody></table></div> : <div className="empty"><KeyRound size={26} /><h3>尚无凭据</h3><p>请添加完整的 ChatGPT Session JSON。</p></div>}</section>
    {open && <div className="dialog-layer" onMouseDown={e => e.target === e.currentTarget && setOpen(false)}><div className="dialog"><div className="dialog-head"><div><h3>添加凭据</h3><p>粘贴完整的 ChatGPT Session JSON</p></div><button className="icon-button" onClick={() => setOpen(false)} title="关闭"><X size={19} /></button></div><div className="dialog-body"><label htmlFor="credential">Session JSON</label><textarea id="credential" value={content} onChange={e => setContent(e.target.value)} placeholder={'包含 accessToken、sessionToken、account.id 和 user.email'} autoFocus /><div className="secure-note"><ShieldCheck size={15} />SessionToken 用于 AccessToken 过期后的透明更新</div></div><div className="dialog-actions"><button className="button button-secondary" onClick={() => setOpen(false)}>取消</button><button className="button button-primary" onClick={add} disabled={busy || !content.trim()}>{busy ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}添加</button></div></div></div>}
    {detail && <div className="dialog-layer" onMouseDown={e => e.target === e.currentTarget && setDetail(null)}><div className="dialog detail-dialog"><div className="dialog-head"><div><h3>查看 Session JSON</h3><p>当前凭据内容，仅在管理会话中显示</p></div><button className="icon-button" onClick={() => setDetail(null)} title="关闭"><X size={19} /></button></div><div className="dialog-body"><pre className="json-view">{JSON.stringify(detail, null, 2)}</pre></div><div className="dialog-actions"><button className="button button-secondary" onClick={() => navigator.clipboard.writeText(JSON.stringify(detail, null, 2)).then(() => notify('JSON 已复制'))}><Database size={16} />复制 JSON</button><button className="button button-primary" onClick={() => setDetail(null)}>关闭</button></div></div></div>}
  </div>
}

function Models({ models, refresh, loading }) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => models.filter(model => `${model.id} ${model.name}`.toLowerCase().includes(query.toLowerCase())), [models, query])
  return <div className="view-content"><div className="view-heading"><div><h2>官网模型</h2><p>模型 ID 直接使用 ChatGPT 官网返回的 slug</p></div><button className="button button-secondary" onClick={() => refresh(true)} disabled={loading}><RefreshCw className={loading ? 'spin' : ''} size={16} />同步官网</button></div>
    <section className="surface table-surface"><div className="model-toolbar"><div className="search"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索模型名称或 slug" /></div><span>{filtered.length} / {models.length} 个模型</span></div>{loading && !models.length ? <div className="empty"><LoaderCircle className="spin" size={26} /><h3>正在读取官网目录</h3></div> : <div className="table-scroll"><table><thead><tr><th>官网 slug</th><th>显示名称</th><th>上下文</th><th>归属</th></tr></thead><tbody>{filtered.map(model => <tr key={model.id}><td><code>{model.id}</code></td><td><strong>{model.name || model.id}</strong><small>{model.description}</small></td><td>{model.max_tokens ? Number(model.max_tokens).toLocaleString() : '—'}</td><td><span className="provider"><RiBrainAi3Line />{model.owned_by}</span></td></tr>)}</tbody></table></div>}</section>
  </div>
}

function Playground({ models, notify }) {
  const [model, setModel] = useState(models[0]?.id || ''); const [input, setInput] = useState(''); const [messages, setMessages] = useState([]); const [busy, setBusy] = useState(false)
  useEffect(() => { if (!model && models[0]) setModel(models[0].id) }, [models, model])
  async function send() { const content=input.trim(); if (!content || busy || !model) return; const next=[...messages,{role:'user',content}]; setMessages(next); setInput(''); setBusy(true); try { const result=await request('/playground/chat',{method:'POST',body:JSON.stringify({model,messages:next})}); const answer=result.choices?.[0]?.message?.content || '未收到模型回复'; setMessages([...next,{role:'assistant',content:answer}]) } catch(e) { notify(e.message,true) } finally { setBusy(false) } }
  return <div className="view-content playground-content"><div className="view-heading"><div><h2>游乐场</h2><p>使用当前账号池直接测试官网模型</p></div><div className="playground-tools"><label>模型<select value={model} onChange={e=>setModel(e.target.value)}>{models.map(item=><option key={item.id} value={item.id}>{item.name || item.id} · {item.id}</option>)}</select></label><button className="button button-secondary" onClick={()=>setMessages([])} disabled={!messages.length}>清空对话</button></div></div><section className="playground-shell"><div className="playground-messages">{messages.length ? messages.map((message,index)=><div className={`play-message ${message.role}`} key={`${message.role}-${index}`}><span className="play-avatar">{message.role==='user'?'你':'AI'}</span><div><small>{message.role==='user'?'用户':'模型'}</small><div className="markdown-body"><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown></div></div></div>) : <div className="play-empty"><span><Waypoints size={22}/></span><h3>开始测试模型</h3><p>选择一个官网模型，输入消息查看真实响应。</p></div>}{busy && <div className="play-message assistant"><span className="play-avatar">AI</span><div><small>模型</small><p className="typing"><i></i><i></i><i></i></p></div></div>}</div><div className="play-input"><textarea value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}} placeholder="输入消息，按 Enter 发送，Shift + Enter 换行" disabled={busy}/><button className="button button-primary" onClick={send} disabled={busy||!input.trim()}>{busy?<LoaderCircle className="spin" size={16}/>:<ChevronRight size={16}/>}发送</button></div></section></div>
}

function App() {
  const [authenticated, setAuthenticated] = useState(null); const [view, setView] = useState('overview'); const [sidebar, setSidebar] = useState(false)
  const [status, setStatus] = useState(null); const [credentials, setCredentials] = useState([]); const [models, setModels] = useState([]); const [loading, setLoading] = useState(false); const [toast, setToast] = useState(null)
  const notify = (message, error = false) => { setToast({ message, error }); setTimeout(() => setToast(null), 2800) }
  const loadStatus = async () => setStatus(await request('/status'))
  const loadCredentials = async () => setCredentials((await request('/credentials')).data)
  const loadModels = async (refresh = false) => { setLoading(true); try { const path = refresh ? '/models/refresh' : '/models'; const result = await request(path, refresh ? { method: 'POST' } : {}); setModels(result.data); if (refresh) notify('模型缓存已更新') } catch (e) { notify(e.message, true) } finally { setLoading(false) } }
  async function bootstrap() { try { await Promise.all([loadStatus(), loadCredentials()]); setAuthenticated(true); loadModels().catch(e => notify(e.message, true)) } catch (e) { if (e.message === 'UNAUTHORIZED') setAuthenticated(false); else notify(e.message, true) } }
  useEffect(() => { bootstrap() }, [])
  async function refreshAll() { setLoading(true); try { await Promise.all([loadStatus(), loadCredentials(), loadModels()]); notify('数据已刷新') } catch (e) { notify(e.message, true) } finally { setLoading(false) } }
  async function logout() { await request('/logout', { method: 'POST' }).catch(() => {}); setAuthenticated(false) }
  if (authenticated === null) return <div className="boot"><SiOpenapiinitiative /><LoaderCircle className="spin" /></div>
  if (!authenticated) return <Login onLogin={bootstrap} />
  return <div className="app-shell"><Sidebar view={view} setView={setView} open={sidebar} close={() => setSidebar(false)} logout={logout} /><main className="workspace"><PageHeader view={view} openMenu={() => setSidebar(true)} />{view === 'overview' && <Overview status={status} modelCount={models.length} refresh={refreshAll} loading={loading} />}{view === 'credentials' && <Credentials credentials={credentials} refresh={loadCredentials} statusRefresh={loadStatus} notify={notify} />}{view === 'models' && <Models models={models} refresh={loadModels} loading={loading} />}{view === 'playground' && <Playground models={models} notify={notify} />}</main>{toast && <div className={`toast ${toast.error ? 'toast-error' : ''}`}>{toast.error ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}{toast.message}</div>}</div>
}

createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>)
