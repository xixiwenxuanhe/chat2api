import { StrictMode, useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Activity, AlertTriangle, Boxes, BrainIcon, CheckCircle2, ChevronDown, ChevronRight, Database,
  Eye, EyeOff, KeyRound, LayoutDashboard, LoaderCircle, LogOut, Menu,
  Plus, RefreshCw, Search, Server, ShieldCheck, SlidersHorizontal, Trash2, Waypoints, X,
} from 'lucide-react'
import { SiOpenapiinitiative } from 'react-icons/si'
import { RiBrainAi3Line } from 'react-icons/ri'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import './styles.css'

const views = {
  overview: { label: '概览', description: '网关与账号池运行状态', icon: LayoutDashboard },
  credentials: { label: '凭据', description: '管理 ChatGPT 账号凭据', icon: KeyRound },
  models: { label: '模型', description: '查看官网实时模型目录', icon: Boxes },
  playground: { label: '游乐场', description: '在网关中直接测试模型', icon: Waypoints },
}

const PLAYGROUND_STORAGE = 'chat2api_playground_messages'
const PLAYGROUND_MODEL_STORAGE = 'chat2api_playground_model'

const formatClock = ms => {
  if (!ms) return ''
  const d = new Date(ms)
  const p = n => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
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

// remark-math v6 only parses `$...$` (inline) and multi-line `$$...$$` (block).
// Models write `\[...\]`; normalize them so they actually render:
//   own-line `\[...\]` -> block `$$...$$`, inline `\[...\]` -> `$...$`.
function normalizeMath(md) {
  return (md || '')
    .replace(/\\\[([\s\S]*?)\\\]/g, (m, inner, offset, full) => {
      const atLineStart = offset === 0 || full[offset - 1] === '\n'
      const atLineEnd = offset + m.length >= full.length || full[offset + m.length] === '\n'
      if (atLineStart && atLineEnd) return '$$\n' + inner + '\n$$'
      return '$' + inner.replace(/\n/g, ' ').trim() + '$'
    })
    .replace(/\\\(([\s\S]*?)\\\)/g, (m, inner) => '$' + inner.replace(/\n/g, ' ').trim() + '$')
}

// remark plugin: fix common LaTeX mistakes from LLM output that break KaTeX
function fixMath() {
  return tree => {
    const visit = node => {
      if (node && typeof node.value === 'string' && (node.type === 'math' || node.type === 'inlineMath')) {
        // `\.` (backslash-dot) is written by models as a period, but KaTeX
        // treats it as the dot-accent and requires an argument -> parse error.
        // Keep the legit accent `\.{x}` intact.
        node.value = node.value.replace(/\\\.(?!\{)/g, '.')
      }
      if (node && Array.isArray(node.children)) node.children.forEach(visit)
    }
    visit(tree)
  }
}

function Playground({ models, notify }) {
  const [model, setModel] = useState(models[0]?.id || ''); const [input, setInput] = useState(''); const [messages, setMessages] = useState([]); const [busy, setBusy] = useState(false); const [showSettings, setShowSettings] = useState(false); const [modelOpen, setModelOpen] = useState(false); const [protocol, setProtocol] = useState('chat.completions')
  const [params, setParams] = useState({ stream: true, temperature: 1, topP: 1, frequencyPenalty: 0, presencePenalty: 0, maxTokens: 4096 })
  const [maxTokensEnabled, setMaxTokensEnabled] = useState(true)
  const composerRef = useRef(null)
  useEffect(() => { if (!model && models[0]) setModel(models[0].id) }, [models, model])
  useEffect(() => {
    try {
      const saved = localStorage.getItem(PLAYGROUND_STORAGE)
      if (saved) {
        const parsed = JSON.parse(saved)
        // drop incomplete assistant placeholders (empty content and reasoning)
        setMessages(parsed.filter(m => !(m.role === 'assistant' && !(m.content || '').trim() && !(m.reasoning || '').trim())))
      }
      const savedModel = localStorage.getItem(PLAYGROUND_MODEL_STORAGE)
      if (savedModel) setModel(savedModel)
    } catch { /* ignore */ }
  }, [])
  useEffect(() => {
    // debounce: during streaming every delta updates messages; only persist
    // once the stream pauses/finishes instead of writing on every token.
    const timer = setTimeout(() => {
      try {
        if (messages.length) localStorage.setItem(PLAYGROUND_STORAGE, JSON.stringify(messages))
        else localStorage.removeItem(PLAYGROUND_STORAGE)
      } catch { /* storage full / unavailable: keep session state */ }
    }, 500)
    return () => clearTimeout(timer)
  }, [messages])
  useEffect(() => {
    try { if (model) localStorage.setItem(PLAYGROUND_MODEL_STORAGE, model) } catch { /* ignore */ }
  }, [model])
  useEffect(() => {
    if (!showSettings && !modelOpen) return
    const onDocClick = e => { if (composerRef.current && !composerRef.current.contains(e.target)) { setShowSettings(false); setModelOpen(false) } }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [showSettings, modelOpen])
  const updateParam = (key, value) => setParams(prev => ({ ...prev, [key]: value }))

  async function send() {
    const content = input.trim(); if (!content || busy || !model) return
    const history = [...messages.filter(m => !(m.role === 'assistant' && !(m.content || '').trim() && !(m.reasoning || '').trim())).map(m => ({ role: m.role, content: m.content })), { role: 'user', content }]
    setMessages([...history, { role: 'assistant', content: '', reasoning: '', reasoningDuration: null }])
    setInput(''); setBusy(true)
    const assistantIndex = history.length
    let reasoningStart = null, contentStart = null, reasoningDone = false
    try {
      const response = await fetch('/admin/api/playground/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, messages: history, protocol, stream: params.stream, temperature: params.temperature, top_p: params.topP, frequency_penalty: params.frequencyPenalty, presence_penalty: params.presencePenalty, ...(maxTokensEnabled ? { max_tokens: params.maxTokens } : {}) }),
      })
      if (!response.ok) {
        let detail = `请求失败 (${response.status})`
        try { detail = (await response.json()).detail || detail } catch { /* ignore */ }
        throw new Error(detail)
      }
      if (!params.stream) {
        const result = await response.json()
        const message = protocol === 'responses'
          ? (result.output || []).find(item => item.type === 'message')?.content?.[0] || {}
          : (result.choices?.[0]?.message || {})
        setMessages(prev => { const list = [...prev]; if (!list[assistantIndex]) return prev; list[assistantIndex] = { ...list[assistantIndex], content: message.text || message.content || '未收到模型回复', reasoning: message.reasoning_content || '' }; return list })
      } else {
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n'); buffer = lines.pop()
          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data:')) continue
            const payload = trimmed.slice(5).trim()
            if (payload === '[DONE]') continue
            let event
            try { event = JSON.parse(payload) } catch { continue }
            const delta = protocol === 'responses'
              ? (event.type === 'response.output_text.delta' ? { content: event.delta || '' } : {})
              : (event.choices?.[0]?.delta || {})
            if (delta.reasoning_content) {
              if (reasoningStart === null) reasoningStart = Date.now()
              setMessages(prev => { const list = [...prev]; if (!list[assistantIndex]) return prev; list[assistantIndex] = { ...list[assistantIndex], reasoning: (list[assistantIndex].reasoning || '') + delta.reasoning_content }; return list })
            }
            if (delta.content) {
              if (reasoningStart !== null && contentStart === null) {
                contentStart = Date.now(); reasoningDone = true
              }
              setMessages(prev => { const list = [...prev]; if (!list[assistantIndex]) return prev; list[assistantIndex] = { ...list[assistantIndex], content: (list[assistantIndex].content || '') + delta.content, reasoningDuration: reasoningDone && reasoningStart ? Math.max(1, Math.round((contentStart - reasoningStart) / 1000)) : list[assistantIndex].reasoningDuration }; return list })
            }
          }
        }
        if (reasoningStart !== null && !reasoningDone) reasoningDone = true
        setMessages(prev => { const list = [...prev]; if (!list[assistantIndex]) return prev; const current = list[assistantIndex]; list[assistantIndex] = { ...current, reasoningDuration: reasoningStart ? (current.reasoningDuration || Math.max(1, Math.round((Date.now() - reasoningStart) / 1000))) : current.reasoningDuration }; return list })
      }
    } catch (e) {
      notify(e.message, true)
      setMessages(prev => { const list = [...prev]; if (list[assistantIndex] && !list[assistantIndex].content && !list[assistantIndex].reasoning) list.splice(assistantIndex, 1); return list })
    } finally { setBusy(false) }
  }

  const markdown = text => <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath, fixMath]} rehypePlugins={[[rehypeKatex, { throwOnError: false }]]}>{normalizeMath(text)}</ReactMarkdown>

  return <div className="view-content playground-content"><section className="playground-shell"><div className="playground-messages">{messages.length ? messages.map((message, index) => <div className={`play-message ${message.role}`} key={`${message.role}-${index}-${message.time || index}`}><span className="play-avatar">{message.role === 'user' ? '你' : 'AI'}</span><div><small>{message.role === 'user' ? '用户' : '模型'}{message.time ? ` · ${formatClock(message.time)}` : ''}</small>{message.role === 'assistant' && message.reasoning ? <details className="play-reasoning" open><summary><BrainIcon size={14} />{message.reasoningDuration ? `思考了 ${message.reasoningDuration} 秒` : busy && index === messages.length - 1 ? '思考中…' : '思考内容'}</summary><div className="markdown-body reasoning-body">{markdown(message.reasoning)}</div></details> : null}{message.role === 'user' ? <div className="markdown-body user-body">{markdown(message.content)}</div> : message.role === 'assistant' && message.content ? <div className="markdown-body">{markdown(message.content)}</div> : message.role === 'assistant' && busy && index === messages.length - 1 ? <p className="typing"><i></i><i></i><i></i></p> : null}</div></div>) : <div className="play-empty"><span><Waypoints size={22} /></span><h3>开始测试模型</h3><p>选择一个官网模型，输入消息查看真实响应。</p></div>}</div><div className="play-composer" ref={composerRef}>{showSettings && <div className="settings-popover"><div className="settings-head"><span className="settings-title"><SlidersHorizontal size={15} />生成参数</span><button className="icon-button" onClick={() => setShowSettings(false)} title="关闭"><X size={15} /></button></div><div className="settings-list"><div className="param-row"><span className="param-label">温度<small>temperature</small></span><input type="range" min="0" max="2" step="0.1" value={params.temperature} onChange={e => updateParam('temperature', Number(e.target.value))} /><span className="param-value">{params.temperature.toFixed(1)}</span></div><div className="param-row"><span className="param-label">Top P<small>top_p</small></span><input type="range" min="0" max="1" step="0.05" value={params.topP} onChange={e => updateParam('topP', Number(e.target.value))} /><span className="param-value">{params.topP.toFixed(2)}</span></div><div className="param-row"><span className="param-label">频率惩罚<small>frequency_penalty</small></span><input type="range" min="-2" max="2" step="0.1" value={params.frequencyPenalty} onChange={e => updateParam('frequencyPenalty', Number(e.target.value))} /><span className="param-value">{params.frequencyPenalty.toFixed(1)}</span></div><div className="param-row"><span className="param-label">存在惩罚<small>presence_penalty</small></span><input type="range" min="-2" max="2" step="0.1" value={params.presencePenalty} onChange={e => updateParam('presencePenalty', Number(e.target.value))} /><span className="param-value">{params.presencePenalty.toFixed(1)}</span></div><div className="param-row"><span className="param-label">最大 Tokens<small>max_tokens</small></span><span className="param-controls"><label className={`play-switch ${maxTokensEnabled ? 'on' : ''}`}><input type="checkbox" checked={maxTokensEnabled} onChange={e => setMaxTokensEnabled(e.target.checked)} /><span className="switch-track"><span className="switch-thumb" /></span></label><input type="number" min="1" step="256" value={params.maxTokens} disabled={!maxTokensEnabled} onChange={e => updateParam('maxTokens', Number(e.target.value))} /></span></div><div className="param-row"><span className="param-label">流式输出<small>stream</small></span><label className={`play-switch ${params.stream ? 'on' : ''}`}><input type="checkbox" checked={params.stream} onChange={e => updateParam('stream', e.target.checked)} /><span className="switch-track"><span className="switch-thumb" /></span></label></div><div className="param-row"><span className="param-label">协议<small>protocol</small></span><select className="protocol-select" value={protocol} onChange={e => setProtocol(e.target.value)} disabled={busy}><option value="chat.completions">Chat Completions</option><option value="responses">Responses</option></select></div></div></div>}<div className="play-input"><textarea value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} placeholder="输入消息，按 Enter 发送，Shift + Enter 换行" disabled={busy} /><div className="play-input-bar"><div className="play-tools"><button className={`icon-button tool-btn ${showSettings ? 'active' : ''}`} onClick={() => setShowSettings(v => !v)} title="生成参数" disabled={busy}><SlidersHorizontal size={17} /></button><button className="icon-button tool-btn" onClick={() => { if (window.confirm('确定清空对话记录？')) setMessages([]) }} disabled={busy || !messages.length} title="清空对话"><Trash2 size={17} /></button></div><div className="play-right"><div className="model-picker"><button className="model-picker-btn" onClick={() => { setModelOpen(v => !v); setShowSettings(false) }} disabled={busy} title="选择模型"><span className="model-picker-text">{models.find(m => m.id === model)?.name || model || '选择模型'}</span><ChevronDown size={14} className={modelOpen ? 'chev-up' : ''} /></button>{modelOpen && <div className="model-menu">{models.map(item => <button key={item.id} className={`model-option ${item.id === model ? 'active' : ''}`} onClick={() => { setModel(item.id); setModelOpen(false) }}><span>{item.name || item.id}</span><small>{item.id}</small></button>)}</div>}</div><button className="button button-primary" onClick={send} disabled={busy || !input.trim()}>{busy ? <LoaderCircle className="spin" size={16} /> : <ChevronRight size={16} />}发送</button></div></div></div></div></section></div>
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
  return <div className="app-shell"><Sidebar view={view} setView={setView} open={sidebar} close={() => setSidebar(false)} logout={logout} /><main className="workspace"><button className="floating-menu" onClick={() => setSidebar(true)} title="打开导航"><Menu size={19} /></button>{view === 'overview' && <Overview status={status} modelCount={models.length} refresh={refreshAll} loading={loading} />}{view === 'credentials' && <Credentials credentials={credentials} refresh={loadCredentials} statusRefresh={loadStatus} notify={notify} />}{view === 'models' && <Models models={models} refresh={loadModels} loading={loading} />}{view === 'playground' && <Playground models={models} notify={notify} />}</main>{toast && <div className={`toast ${toast.error ? 'toast-error' : ''}`}>{toast.error ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}{toast.message}</div>}</div>
}

createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>)
