import { useState } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// USERS
// ─────────────────────────────────────────────────────────────────────────────
const USERS = {
  akadmin: { name:"Admin User",    initials:"AU", role:"Administrator", lastLogin:"2026-03-17T08:00:00Z" },
  jsmith:  { name:"Jane Smith",    initials:"JS", role:"Developer",     lastLogin:"2026-03-16T17:30:00Z" },
  mwilson: { name:"Marcus Wilson", initials:"MW", role:"Analyst",       lastLogin:"2026-03-17T07:20:00Z" },
  lchang:  { name:"Linda Chang",   initials:"LC", role:"Viewer",        lastLogin:"2026-03-15T14:00:00Z" },
};

// Logged-in user for this session
const ME = "akadmin";

// ─────────────────────────────────────────────────────────────────────────────
// TREE
// PAW structure:
//   My Content        — private books owned by the logged-in user only
//   Shared Content    — team folders with shared/admin books
//     ├─ Administration
//     ├─ CST — Healthcare ABC
//     │   ├─ Data Input
//     │   └─ Governance and Audit
//     ├─ Finance Reporting
//     │   └─ Work in Progress
//     └─ Templates
// ─────────────────────────────────────────────────────────────────────────────
const TREE = [
  // ── My Content: private books for each user ──────────────────────────────
  {
    id:"f-my", type:"folder", name:"My Content",
    system:true, owner: ME,
    description:"Your private workspace. Books here are only visible to you.",
    children:[
      {
        id:"bk-my-sandbox", type:"book", name:"ABC Sandbox",
        description:"Personal scratch space for testing allocation scenarios before promoting to shared.",
        createdBy:"akadmin", createdDate:"2026-03-01T10:00:00Z",
        modifiedBy:"akadmin", modifiedDate:"2026-03-17T08:55:00Z",
        status:"Draft", visibility:"Private",
        tabs:[
          { id:"t-my-1", name:"Pool Test",       type:"Cube View", cube:"CST Cost Pool Allocation", view:"Test Scenario", createdBy:"akadmin", modifiedDate:"2026-03-17T08:55:00Z", description:"Testing revised pool splits" },
          { id:"t-my-2", name:"Scratch Notes",   type:"Websheet",  cube:null,                       view:null,            createdBy:"akadmin", modifiedDate:"2026-03-15T11:00:00Z", description:"Working notes and to-do list" },
        ],
      },
      {
        id:"bk-my-recon", type:"book", name:"Recon Workings",
        description:"Private reconciliation workings during month-end close.",
        createdBy:"akadmin", createdDate:"2026-02-28T09:00:00Z",
        modifiedBy:"akadmin", modifiedDate:"2026-03-14T17:30:00Z",
        status:"Draft", visibility:"Private",
        tabs:[
          { id:"t-my-3", name:"March Recon",     type:"Cube View", cube:"CST Allocation Reconciliation", view:"RPT Default",   createdBy:"akadmin", modifiedDate:"2026-03-14T17:30:00Z", description:"March close reconciliation" },
          { id:"t-my-4", name:"Variance Notes",  type:"Websheet",  cube:null,                            view:null,            createdBy:"akadmin", modifiedDate:"2026-03-14T16:00:00Z", description:"Unexplained variances log" },
        ],
      },
    ],
  },

  // ── Shared Content ────────────────────────────────────────────────────────
  {
    id:"f-shared", type:"folder", name:"Shared Content",
    system:true,
    description:"Team content visible to all users with appropriate access.",
    children:[

      // Administration
      {
        id:"f-admin", type:"folder", name:"Administration",
        createdBy:"akadmin", modifiedDate:"2026-03-01T08:00:00Z",
        children:[
          {
            id:"bk-gbl", type:"book", name:"GBL Dimension Management",
            description:"Manage global shared dimensions — accounts, departments, periods, versions.",
            createdBy:"akadmin", createdDate:"2026-01-10T08:00:00Z",
            modifiedBy:"akadmin", modifiedDate:"2026-03-01T12:00:00Z",
            status:"Published", visibility:"Admin",
            tabs:[
              { id:"t-gbl-1", name:"Account Hierarchy", type:"Websheet",  cube:null,              view:null,           createdBy:"akadmin", modifiedDate:"2026-02-28T10:00:00Z", description:"Chart of accounts 4000–7000" },
              { id:"t-gbl-2", name:"Department Setup",  type:"Cube View", cube:"GBL Assumptions", view:"Dept Input",   createdBy:"akadmin", modifiedDate:"2026-02-01T09:00:00Z", description:"D001–D017 organisational units" },
              { id:"t-gbl-3", name:"Period Calendar",   type:"Websheet",  cube:null,              view:null,           createdBy:"akadmin", modifiedDate:"2026-01-15T09:00:00Z", description:"FY periods Apr–Mar, MTD/YTG/OBL" },
              { id:"t-gbl-4", name:"Version Control",   type:"Cube View", cube:"GBL Assumptions", view:"Version Ctrl", createdBy:"akadmin", modifiedDate:"2026-02-10T14:00:00Z", description:"Budget / Forecast / Actual states" },
            ],
          },
          {
            id:"bk-ti", type:"book", name:"TI Process Monitor",
            description:"Turbo Integrator process catalogue — run history, error logs, scheduling.",
            createdBy:"akadmin", createdDate:"2026-01-20T08:00:00Z",
            modifiedBy:"akadmin", modifiedDate:"2026-03-10T09:00:00Z",
            status:"Published", visibility:"Admin",
            tabs:[
              { id:"t-ti-1", name:"Process Catalogue", type:"Websheet", cube:null, view:null, createdBy:"akadmin", modifiedDate:"2026-03-10T09:00:00Z", description:"All TI processes with descriptions" },
              { id:"t-ti-2", name:"Chore Schedule",    type:"Websheet", cube:null, view:null, createdBy:"akadmin", modifiedDate:"2026-03-01T08:00:00Z", description:"Scheduled chore timings" },
              { id:"t-ti-3", name:"Error Log",         type:"Websheet", cube:null, view:null, createdBy:"akadmin", modifiedDate:"2026-03-17T06:00:00Z", description:"TI error history and severity" },
            ],
          },
        ],
      },

      // CST — Healthcare ABC
      {
        id:"f-cst", type:"folder", name:"CST — Healthcare ABC",
        createdBy:"akadmin", modifiedDate:"2026-03-14T16:00:00Z",
        children:[
          {
            id:"f-cst-input", type:"folder", name:"Data Input",
            createdBy:"akadmin", modifiedDate:"2026-03-14T14:00:00Z",
            children:[
              {
                id:"bk-abc", type:"book", name:"Healthcare ABC Model",
                description:"Activity-Based Costing model for healthcare overhead allocation across service lines.",
                createdBy:"akadmin", createdDate:"2026-01-15T09:22:00Z",
                modifiedBy:"akadmin", modifiedDate:"2026-03-14T16:45:00Z",
                status:"Published", visibility:"Shared",
                tabs:[
                  { id:"t-abc-1",  name:"Overview",               type:"Websheet",  cube:null,                            view:null,          createdBy:"akadmin", modifiedDate:"2026-03-10T10:00:00Z", description:"Model navigation and map" },
                  { id:"t-abc-2",  name:"GL Input",               type:"Cube View", cube:"CST GL Input",                  view:"RPT Default", createdBy:"akadmin", modifiedDate:"2026-03-12T14:22:00Z", description:"Raw GL overhead cost entry" },
                  { id:"t-abc-3",  name:"Pool Drivers",           type:"Cube View", cube:"CST Pool Driver",               view:"RPT Default", createdBy:"akadmin", modifiedDate:"2026-03-12T14:30:00Z", description:"Cost pool allocation %" },
                  { id:"t-abc-4",  name:"Activity Drivers",       type:"Cube View", cube:"CST Activity Driver",           view:"RPT Default", createdBy:"jsmith",  modifiedDate:"2026-03-13T09:15:00Z", description:"Activity allocation %" },
                  { id:"t-abc-5",  name:"Stage 1 — Pools",        type:"Cube View", cube:"CST Cost Pool Allocation",      view:"RPT Default", createdBy:"akadmin", modifiedDate:"2026-03-14T11:00:00Z", description:"Stage 1: GL costs → 9 cost pools" },
                  { id:"t-abc-6",  name:"Stage 2 — Activities",   type:"Cube View", cube:"CST Activity Allocation",       view:"RPT Default", createdBy:"akadmin", modifiedDate:"2026-03-14T11:05:00Z", description:"Stage 2: pools → 11 activities" },
                  { id:"t-abc-7",  name:"Stage 3 — Service Lines",type:"Cube View", cube:"CST Service Line Cost",         view:"RPT Default", createdBy:"akadmin", modifiedDate:"2026-03-14T11:10:00Z", description:"Stage 3: activities → 8 service lines" },
                  { id:"t-abc-8",  name:"P&L Report",             type:"Cube View", cube:"CST Profit and Loss Report",    view:"RPT Default", createdBy:"mwilson", modifiedDate:"2026-03-16T08:40:00Z", description:"Before vs After ABC comparison" },
                  { id:"t-abc-9",  name:"Reconciliation",         type:"Cube View", cube:"CST Allocation Reconciliation", view:"RPT Default", createdBy:"akadmin", modifiedDate:"2026-03-14T11:20:00Z", description:"Audit: cost in = cost out" },
                  { id:"t-abc-10", name:"Config",                 type:"Cube View", cube:"CST Allocation Config",         view:"RPT Default", createdBy:"akadmin", modifiedDate:"2026-02-20T09:00:00Z", description:"Version-aware model settings" },
                ],
              },
            ],
          },
          {
            id:"f-cst-gov", type:"folder", name:"Governance and Audit",
            createdBy:"mwilson", modifiedDate:"2026-03-17T07:30:00Z",
            children:[
              {
                id:"bk-gov", type:"book", name:"CST Governance Dashboard",
                description:"Operational monitoring — reconciliation status, data quality alerts, allocation run history.",
                createdBy:"mwilson", createdDate:"2026-02-01T11:00:00Z",
                modifiedBy:"mwilson", modifiedDate:"2026-03-17T07:30:00Z",
                status:"Draft", visibility:"Shared",
                tabs:[
                  { id:"t-gov-1", name:"Run Status",   type:"Websheet",  cube:null,                           view:null,            createdBy:"mwilson", modifiedDate:"2026-03-17T07:30:00Z", description:"Latest allocation chore results" },
                  { id:"t-gov-2", name:"Recon Checks", type:"Cube View", cube:"CST Allocation Reconciliation", view:"Audit Summary", createdBy:"mwilson", modifiedDate:"2026-03-17T07:25:00Z", description:"Balance checks at each stage" },
                  { id:"t-gov-3", name:"Data Quality", type:"Websheet",  cube:null,                           view:null,            createdBy:"mwilson", modifiedDate:"2026-03-15T16:00:00Z", description:"Record counts and anomalies" },
                ],
              },
            ],
          },
        ],
      },

      // Finance Reporting
      {
        id:"f-finance", type:"folder", name:"Finance Reporting",
        createdBy:"jsmith", modifiedDate:"2026-03-16T17:00:00Z",
        children:[
          {
            id:"bk-fin", type:"book", name:"Finance Reporting Suite",
            description:"Executive-facing reports — P&L by service line, variance analysis, period comparisons.",
            createdBy:"jsmith", createdDate:"2026-02-15T09:00:00Z",
            modifiedBy:"jsmith", modifiedDate:"2026-03-16T17:00:00Z",
            status:"Published", visibility:"Shared",
            tabs:[
              { id:"t-fin-1", name:"Executive Summary",   type:"Websheet",  cube:null,                       view:null,             createdBy:"jsmith", modifiedDate:"2026-03-16T17:00:00Z", description:"KPI scorecard for CFO" },
              { id:"t-fin-2", name:"P&L by Service Line", type:"Cube View", cube:"CST Profit and Loss Report",view:"SL Summary",    createdBy:"jsmith", modifiedDate:"2026-03-16T16:45:00Z", description:"8 service line P&L comparison" },
              { id:"t-fin-3", name:"Budget vs Actual",    type:"Cube View", cube:"CST Service Line Cost",     view:"BvA Variance",   createdBy:"jsmith", modifiedDate:"2026-03-16T16:30:00Z", description:"Period variance analysis" },
              { id:"t-fin-4", name:"Trend Analysis",      type:"Cube View", cube:"CST Service Line Cost",     view:"12 Month Trend", createdBy:"jsmith", modifiedDate:"2026-03-14T09:00:00Z", description:"12-month rolling view" },
              { id:"t-fin-5", name:"Currency Bridge",     type:"Cube View", cube:"GBL Assumptions",           view:"FX Bridge",      createdBy:"jsmith", modifiedDate:"2026-02-28T11:00:00Z", description:"Multi-currency translation" },
            ],
          },
          {
            id:"f-wip", type:"folder", name:"Work in Progress",
            createdBy:"jsmith", modifiedDate:"2026-03-10T11:00:00Z",
            children:[
              {
                id:"bk-draft", type:"book", name:"Q2 Cost Review",
                description:"Draft analysis of Q2 cost variances — not yet published.",
                createdBy:"jsmith", createdDate:"2026-03-05T09:00:00Z",
                modifiedBy:"jsmith", modifiedDate:"2026-03-10T11:00:00Z",
                status:"Draft", visibility:"Shared",
                tabs:[
                  { id:"t-dr-1", name:"Q2 Overview",    type:"Websheet",  cube:null,                        view:null,        createdBy:"jsmith", modifiedDate:"2026-03-10T11:00:00Z", description:"Q2 narrative summary" },
                  { id:"t-dr-2", name:"Pool Variances",  type:"Cube View", cube:"CST Cost Pool Allocation",  view:"Q2 Drill", createdBy:"jsmith", modifiedDate:"2026-03-10T10:30:00Z", description:"Pool-level variance detail" },
                ],
              },
            ],
          },
        ],
      },

      // Templates
      {
        id:"f-templates", type:"folder", name:"Templates",
        createdBy:"akadmin", modifiedDate:"2026-02-01T09:00:00Z",
        children:[
          {
            id:"bk-tmpl", type:"book", name:"Standard Input Template",
            description:"Reusable input template for new CST modules.",
            createdBy:"akadmin", createdDate:"2026-01-05T09:00:00Z",
            modifiedBy:"akadmin", modifiedDate:"2026-02-01T09:00:00Z",
            status:"Published", visibility:"Shared",
            tabs:[
              { id:"t-tmpl-1", name:"Input Form",  type:"Websheet",  cube:null,              view:null,         createdBy:"akadmin", modifiedDate:"2026-02-01T09:00:00Z", description:"Generic data entry layout" },
              { id:"t-tmpl-2", name:"Audit Trail", type:"Cube View", cube:"GBL Assumptions", view:"Audit View", createdBy:"akadmin", modifiedDate:"2026-01-20T09:00:00Z", description:"Change tracking view" },
            ],
          },
        ],
      },
    ],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────
const NOW = new Date("2026-03-17T09:00:00Z");
function relTime(iso) {
  const diff = Math.floor((NOW - new Date(iso)) / 1000);
  if (diff < 60)    return "just now";
  if (diff < 3600)  return Math.floor(diff/60) + "m ago";
  if (diff < 86400) return Math.floor(diff/3600) + "h ago";
  const d = Math.floor(diff/86400);
  if (d < 30)       return d + "d ago";
  return new Date(iso).toLocaleDateString("en-NZ",{day:"numeric",month:"short",year:"numeric"});
}
function fmtDate(iso) {
  return new Date(iso).toLocaleString("en-NZ",{day:"numeric",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"});
}
function countBooks(node) {
  if (node.type === "book") return 1;
  return (node.children||[]).reduce((s,c) => s + countBooks(c), 0);
}
function flatten(nodes, path=[]) {
  return nodes.flatMap(n => {
    const here = { ...n, _path:[...path, n.name] };
    if (n.children) return [here, ...flatten(n.children, [...path, n.name])];
    return [here];
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// COLOURS
// ─────────────────────────────────────────────────────────────────────────────
const C = {
  bg:"#0d1117", surface:"#161b22", card:"#1c2230",
  border:"#30363d", faint:"#21262d",
  text:"#e6edf3", muted:"#8b949e",
  blue:"#388bfd", purple:"#a371f7", amber:"#e3b341",
  teal:"#3fb950", coral:"#f78166", gray:"#6e7681",
  pink:"#f778ba",
};

const statusColor = s => s==="Published" ? C.teal : s==="Draft" ? C.amber : C.gray;
const visColor    = v => v==="Admin" ? C.coral : v==="Private" ? C.pink : C.blue;
const userAccent  = uid => [C.blue, C.purple, C.teal, C.coral, C.amber][uid.charCodeAt(0) % 5];

// ─────────────────────────────────────────────────────────────────────────────
// ICONS
// ─────────────────────────────────────────────────────────────────────────────
function FolderIcon({ open, isPrivate, isSystem }) {
  const fill = isPrivate ? C.pink : isSystem ? C.purple : C.amber;
  return (
    <svg width="14" height="13" viewBox="0 0 16 14" fill="none" style={{flexShrink:0}}>
      <path d="M1 3a1 1 0 011-1h4l1.5 1.5H14a1 1 0 011 1v7a1 1 0 01-1 1H2a1 1 0 01-1-1V3z"
        fill={fill} fillOpacity={open ? 0.85 : 0.25}
        stroke={fill} strokeWidth="0.7"/>
    </svg>
  );
}

function BookIcon({ color=C.blue }) {
  return (
    <svg width="12" height="14" viewBox="0 0 12 14" fill="none" style={{flexShrink:0}}>
      <rect x="1.5" y="1" width="9" height="12" rx="1.5"
        fill={color} fillOpacity="0.18" stroke={color} strokeWidth="0.75"/>
      <line x1="4" y1="4.5" x2="8" y2="4.5" stroke={color} strokeWidth="0.75"/>
      <line x1="4" y1="6.5" x2="8" y2="6.5" stroke={color} strokeWidth="0.75"/>
      <line x1="4" y1="8.5" x2="6.5" y2="8.5" stroke={color} strokeWidth="0.75"/>
    </svg>
  );
}

function TabIcon({ type }) {
  const c = type === "Cube View" ? C.blue : C.purple;
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{flexShrink:0}}>
      <rect x="1" y="1" width="10" height="10" rx="1.5"
        fill={c} fillOpacity="0.15" stroke={c} strokeWidth="0.7"/>
      {type === "Cube View"
        ? <><line x1="3" y1="6" x2="9" y2="6" stroke={c} strokeWidth="0.7"/>
             <line x1="6" y1="3" x2="6" y2="9" stroke={c} strokeWidth="0.7"/></>
        : <><line x1="3" y1="4"   x2="9" y2="4"   stroke={c} strokeWidth="0.7"/>
             <line x1="3" y1="6.5" x2="9" y2="6.5" stroke={c} strokeWidth="0.7"/>
             <line x1="3" y1="9"   x2="6" y2="9"   stroke={c} strokeWidth="0.7"/></>
      }
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="9" height="10" viewBox="0 0 9 10" fill="none" style={{flexShrink:0}}>
      <rect x="1" y="4.5" width="7" height="5" rx="1" fill={C.pink} fillOpacity="0.3" stroke={C.pink} strokeWidth="0.7"/>
      <path d="M2.5 4.5V3a2 2 0 014 0v1.5" stroke={C.pink} strokeWidth="0.7" fill="none"/>
    </svg>
  );
}

function ChevronIcon({ open }) {
  return (
    <svg width="9" height="9" viewBox="0 0 9 9" fill="none"
      style={{flexShrink:0, transition:"transform 0.15s", transform: open ? "rotate(90deg)" : "rotate(0deg)"}}>
      <path d="M3 2l3 2.5L3 7" stroke={C.muted} strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SMALL COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────
function Badge({ label, color }) {
  return (
    <span style={{
      display:"inline-block", padding:"2px 7px", borderRadius:4,
      fontSize:10, fontWeight:600, letterSpacing:"0.05em", textTransform:"uppercase",
      background:color+"22", color, border:`1px solid ${color}44`,
    }}>{label}</span>
  );
}

function Avatar({ userId, size=26 }) {
  const u = USERS[userId];
  const c = userAccent(userId);
  return (
    <div style={{display:"flex", alignItems:"center", gap:8}}>
      <div style={{
        width:size, height:size, borderRadius:"50%", flexShrink:0,
        background:c+"28", border:`1px solid ${c}55`,
        display:"flex", alignItems:"center", justifyContent:"center",
        fontSize:size*0.38, fontWeight:600, color:c,
      }}>{u?.initials || userId.slice(0,2).toUpperCase()}</div>
      <div>
        <div style={{fontSize:12, color:C.text, lineHeight:1.3}}>{u?.name || userId}</div>
        <div style={{fontSize:10, color:C.muted}}>{u?.role}</div>
      </div>
    </div>
  );
}

function Meta({ label, value, mono, full }) {
  return (
    <div style={{gridColumn: full ? "1/-1" : undefined}}>
      <div style={{fontSize:10, color:C.muted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3}}>{label}</div>
      <div style={{fontSize:12, color:C.text, fontFamily: mono ? "'DM Mono',monospace" : undefined, lineHeight:1.4}}>{value}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TREE NODE
// ─────────────────────────────────────────────────────────────────────────────
function TreeNode({ node, depth, selectedId, onSelect, openIds, toggleOpen }) {
  const isOpen  = openIds.has(node.id);
  const isSel   = selectedId === node.id;
  const hasKids = (node.children||[]).length > 0;
  const bkCount = node.type === "folder" ? countBooks(node) : null;
  const isPrivateFolder = node.id === "f-my";

  return (
    <div>
      <div
        onClick={() => { onSelect(node); if (node.type === "folder") toggleOpen(node.id); }}
        style={{
          display:"flex", alignItems:"center", gap:5,
          padding:`3px 8px 3px ${8 + depth * 14}px`,
          cursor:"pointer", borderRadius:4, marginBottom:1,
          background: isSel ? C.blue+"1a" : "transparent",
          borderLeft: isSel ? `2px solid ${C.blue}` : "2px solid transparent",
          transition:"background 0.1s",
        }}
        onMouseEnter={e => { if (!isSel) e.currentTarget.style.background = "#ffffff08"; }}
        onMouseLeave={e => { if (!isSel) e.currentTarget.style.background = "transparent"; }}
      >
        <span style={{width:9, flexShrink:0}}>
          {hasKids && <ChevronIcon open={isOpen}/>}
        </span>

        {node.type === "folder"
          ? <FolderIcon open={isOpen} isPrivate={isPrivateFolder} isSystem={node.system}/>
          : <BookIcon color={statusColor(node.status)}/>
        }

        <span style={{
          flex:1, fontSize:12, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
          color: isSel ? C.text : node.type === "folder" ? "#cdd9e5" : "#adbac7",
          fontWeight: node.type === "folder" ? 500 : 400,
          marginLeft:2,
        }}>{node.name}</span>

        {/* Private folder lock icon */}
        {isPrivateFolder && <LockIcon/>}

        {/* Book status dot */}
        {node.type === "book" && (
          <span style={{width:6, height:6, borderRadius:"50%", background:statusColor(node.status), flexShrink:0}}/>
        )}

        {/* Folder book count */}
        {node.type === "folder" && bkCount > 0 && (
          <span style={{fontSize:9, color:C.muted, background:C.faint, padding:"1px 4px", borderRadius:6, flexShrink:0}}>
            {bkCount}
          </span>
        )}
      </div>

      {hasKids && isOpen && node.children.map(child => (
        <TreeNode key={child.id} node={child} depth={depth+1}
          selectedId={selectedId} onSelect={onSelect}
          openIds={openIds} toggleOpen={toggleOpen}/>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// DETAIL PANEL
// ─────────────────────────────────────────────────────────────────────────────
function DetailPanel({ node }) {
  const [selTabId, setSelTabId] = useState(null);

  // Empty state
  if (!node) return (
    <div style={{display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", height:"100%", gap:10, color:C.muted}}>
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        <rect x="5" y="5" width="30" height="30" rx="6" stroke={C.muted} strokeWidth="1" strokeDasharray="3 2"/>
        <path d="M13 20h14M20 13v14" stroke={C.muted} strokeWidth="1" strokeLinecap="round"/>
      </svg>
      <span style={{fontSize:12}}>Select a folder or book</span>
    </div>
  );

  // ── Folder detail ──
  if (node.type === "folder") {
    const books      = (node.children||[]).filter(c => c.type === "book");
    const subfolders = (node.children||[]).filter(c => c.type === "folder");
    const total      = countBooks(node);
    const isPrivate  = node.id === "f-my";

    return (
      <div style={{padding:"18px 22px", overflowY:"auto", height:"100%"}}>
        {/* Header */}
        <div style={{display:"flex", alignItems:"center", gap:10, marginBottom:14}}>
          <FolderIcon open={true} isPrivate={isPrivate} isSystem={node.system}/>
          <div>
            <div style={{display:"flex", alignItems:"center", gap:8}}>
              <span style={{fontWeight:600, fontSize:15, color:C.text}}>{node.name}</span>
              {isPrivate && <Badge label="Private" color={C.pink}/>}
              {node.system && !isPrivate && <Badge label="System" color={C.purple}/>}
            </div>
            <div style={{fontSize:11, color:C.muted, marginTop:2}}>
              {total} book{total !== 1 ? "s" : ""} · {(node.children||[]).length} items
            </div>
          </div>
        </div>

        {/* Private folder notice */}
        {isPrivate && (
          <div style={{
            background:C.pink+"0f", border:`1px solid ${C.pink}33`,
            borderRadius:8, padding:"10px 14px", marginBottom:16,
            display:"flex", alignItems:"flex-start", gap:10,
          }}>
            <LockIcon/>
            <div>
              <div style={{fontSize:12, color:C.pink, fontWeight:500, marginBottom:2}}>Private workspace</div>
              <div style={{fontSize:11, color:C.muted, lineHeight:1.5}}>
                {node.description} Books here are owned by <strong style={{color:C.text}}>{USERS[ME]?.name}</strong> and not visible to other users.
              </div>
            </div>
          </div>
        )}

        {/* Owner / modified */}
        {node.createdBy && (
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:18,
            background:C.card, border:`1px solid ${C.border}`, borderRadius:8, padding:14}}>
            <div>
              <div style={{fontSize:10, color:C.muted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:4}}>Owner</div>
              <Avatar userId={node.createdBy}/>
            </div>
            <Meta label="Last modified" value={relTime(node.modifiedDate||"")}/>
          </div>
        )}

        {/* Subfolders */}
        {subfolders.length > 0 && (
          <div style={{marginBottom:16}}>
            <div style={{fontSize:10, color:C.muted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:7}}>
              Subfolders · {subfolders.length}
            </div>
            {subfolders.map(f => (
              <div key={f.id} style={{display:"flex", alignItems:"center", gap:8,
                padding:"7px 10px", background:C.card, border:`1px solid ${C.border}`,
                borderRadius:6, marginBottom:3}}>
                <FolderIcon open={false}/>
                <span style={{fontSize:12, color:C.text, flex:1}}>{f.name}</span>
                <span style={{fontSize:10, color:C.muted}}>
                  {countBooks(f)} book{countBooks(f) !== 1 ? "s" : ""}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Books */}
        {books.length > 0 && (
          <div>
            <div style={{fontSize:10, color:C.muted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:7}}>
              Books · {books.length}
            </div>
            {books.map(b => (
              <div key={b.id} style={{display:"flex", alignItems:"center", gap:8,
                padding:"8px 10px", background:C.card, border:`1px solid ${C.border}`,
                borderRadius:6, marginBottom:3}}>
                <BookIcon color={statusColor(b.status)}/>
                <div style={{flex:1, minWidth:0}}>
                  <div style={{fontSize:12, color:C.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>
                    {b.name}
                  </div>
                  <div style={{fontSize:10, color:C.muted}}>
                    {b.tabs.length} pages · {USERS[b.createdBy]?.name || b.createdBy} · {relTime(b.modifiedDate)}
                  </div>
                </div>
                <Badge label={b.status} color={statusColor(b.status)}/>
                {b.visibility === "Private" && <LockIcon/>}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── Book detail ──
  if (node.type === "book") {
    const isPrivate = node.visibility === "Private";
    return (
      <div style={{display:"flex", flexDirection:"column", height:"100%", overflow:"hidden"}}>

        {/* Book header */}
        <div style={{padding:"16px 20px", borderBottom:`1px solid ${C.border}`, flexShrink:0}}>
          <div style={{display:"flex", alignItems:"flex-start", gap:10, marginBottom:10}}>
            <div style={{marginTop:2}}><BookIcon color={C.blue}/></div>
            <div style={{flex:1, minWidth:0}}>
              <div style={{fontWeight:600, fontSize:14.5, color:C.text, marginBottom:4}}>{node.name}</div>
              <div style={{fontSize:11, color:C.muted, lineHeight:1.5}}>{node.description}</div>
            </div>
          </div>
          <div style={{display:"flex", gap:5, flexWrap:"wrap", alignItems:"center"}}>
            <Badge label={node.status}     color={statusColor(node.status)}/>
            <Badge label={node.visibility} color={visColor(node.visibility)}/>
            <span style={{padding:"2px 7px", borderRadius:4, fontSize:10, color:C.muted,
              background:C.faint, border:`1px solid ${C.border}`}}>
              {node.tabs.length} pages
            </span>
            {isPrivate && (
              <span style={{display:"flex", alignItems:"center", gap:4, fontSize:10, color:C.pink}}>
                <LockIcon/> Only visible to you
              </span>
            )}
          </div>
        </div>

        {/* Metadata */}
        <div style={{padding:"14px 20px", borderBottom:`1px solid ${C.border}`, flexShrink:0,
          display:"grid", gridTemplateColumns:"1fr 1fr", gap:"12px 16px"}}>
          <div>
            <div style={{fontSize:10, color:C.muted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:4}}>Created by</div>
            <Avatar userId={node.createdBy}/>
          </div>
          <div>
            <div style={{fontSize:10, color:C.muted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:4}}>Last modified by</div>
            <Avatar userId={node.modifiedBy}/>
          </div>
          <Meta label="Created"       value={fmtDate(node.createdDate)}/>
          <Meta label="Last modified" value={fmtDate(node.modifiedDate)}/>
        </div>

        {/* Pages list */}
        <div style={{flex:1, overflowY:"auto", padding:"12px 20px"}}>
          <div style={{fontSize:10, color:C.muted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:8}}>
            Pages · {node.tabs.length}
          </div>

          {node.tabs.map((tab, i) => {
            const isSel = selTabId === tab.id;
            return (
              <div key={tab.id} style={{marginBottom:2}}>
                <div
                  onClick={() => setSelTabId(id => id === tab.id ? null : tab.id)}
                  style={{
                    display:"flex", alignItems:"center", gap:8, padding:"6px 10px",
                    borderRadius:6, cursor:"pointer",
                    background: isSel ? C.blue+"14" : "transparent",
                    border: isSel ? `1px solid ${C.blue}33` : "1px solid transparent",
                    transition:"background 0.1s",
                  }}
                  onMouseEnter={e => { if (!isSel) e.currentTarget.style.background = "#ffffff08"; }}
                  onMouseLeave={e => { if (!isSel) e.currentTarget.style.background = "transparent"; }}
                >
                  <span style={{fontSize:10, color:C.muted, width:18, textAlign:"right",
                    fontFamily:"'DM Mono',monospace", flexShrink:0}}>{i+1}</span>
                  <TabIcon type={tab.type}/>
                  <div style={{flex:1, minWidth:0}}>
                    <div style={{fontSize:12.5, color: isSel ? C.blue : C.text,
                      overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{tab.name}</div>
                    <div style={{fontSize:10.5, color:C.muted}}>
                      {tab.type}{tab.cube ? ` · ${tab.cube}` : ""}
                    </div>
                  </div>
                  <div style={{fontSize:10, color:C.muted, whiteSpace:"nowrap", flexShrink:0}}>
                    {relTime(tab.modifiedDate)}
                  </div>
                  <svg width="9" height="9" viewBox="0 0 9 9" fill="none"
                    style={{flexShrink:0, transition:"transform 0.15s", transform: isSel ? "rotate(90deg)" : "rotate(0deg)"}}>
                    <path d="M3 2l3 2.5L3 7" stroke={C.muted} strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>

                {isSel && (
                  <div style={{margin:"4px 0 6px 36px", background:C.surface,
                    border:`1px solid ${C.border}`, borderRadius:8, padding:"12px 14px"}}>
                    <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:"10px 16px"}}>
                      <Meta label="Page type"   value={tab.type}/>
                      <div>
                        <div style={{fontSize:10, color:C.muted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:4}}>Owner</div>
                        <Avatar userId={tab.createdBy} size={22}/>
                      </div>
                      <Meta label="Source cube" value={tab.cube || "Websheet (native)"} mono/>
                      <Meta label="View name"   value={tab.view || "—"} mono/>
                      <Meta label="Modified"    value={fmtDate(tab.modifiedDate)}/>
                      <div/>
                      <Meta label="Description" value={tab.description} full/>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// SEARCH
// ─────────────────────────────────────────────────────────────────────────────
function SearchResults({ query, onSelect }) {
  const q   = query.toLowerCase();
  const all = flatten(TREE);
  const hits = all.filter(n =>
    n.name.toLowerCase().includes(q) ||
    (n.description||"").toLowerCase().includes(q) ||
    (n.createdBy||"").toLowerCase().includes(q) ||
    (n.tabs||[]).some(t => t.name.toLowerCase().includes(q) || (t.cube||"").toLowerCase().includes(q))
  ).slice(0, 25);

  return (
    <div style={{padding:"4px 0"}}>
      <div style={{fontSize:10, color:C.muted, padding:"0 10px 6px",
        textTransform:"uppercase", letterSpacing:"0.06em"}}>{hits.length} results</div>
      {hits.map(n => (
        <div key={n.id} onClick={() => onSelect(n)}
          style={{display:"flex", alignItems:"center", gap:8, padding:"5px 10px", cursor:"pointer", borderRadius:4}}
          onMouseEnter={e => e.currentTarget.style.background = "#ffffff0a"}
          onMouseLeave={e => e.currentTarget.style.background = "transparent"}
        >
          {n.type === "folder"
            ? <FolderIcon open={false} isPrivate={n.id==="f-my"}/>
            : <BookIcon color={statusColor(n.status)}/>
          }
          <div style={{minWidth:0}}>
            <div style={{fontSize:12, color:C.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{n.name}</div>
            <div style={{fontSize:10, color:C.muted}}>{n._path.slice(0,-1).join(" › ")}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// APP
// ─────────────────────────────────────────────────────────────────────────────
export default function App() {
  const [openIds,  setOpenIds]  = useState(new Set(["f-my", "f-shared", "f-cst"]));
  const [selected, setSelected] = useState(null);
  const [search,   setSearch]   = useState("");

  function toggleOpen(id) {
    setOpenIds(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }
  function handleSelect(node) { setSelected(node); setSearch(""); }

  const allFlat  = flatten(TREE);
  const allBooks = allFlat.filter(n => n.type === "book");
  const allTabs  = allBooks.flatMap(b => b.tabs || []);
  const myBooks  = allBooks.filter(b => b.visibility === "Private");
  const sharedBooks = allBooks.filter(b => b.visibility !== "Private");

  return (
    <div style={{
      background:C.bg, color:C.text,
      fontFamily:"'DM Sans',system-ui,sans-serif",
      fontSize:14, lineHeight:1.5,
      height:"100vh", display:"flex", flexDirection:"column",
    }}>
      {/* Top bar */}
      <div style={{
        background:C.surface, borderBottom:`1px solid ${C.border}`,
        display:"flex", alignItems:"center", gap:16,
        padding:"0 16px", height:44, flexShrink:0,
      }}>
        <div style={{display:"flex", alignItems:"center", gap:8}}>
          <div style={{
            width:22, height:22, borderRadius:5,
            background:`linear-gradient(135deg,${C.blue},${C.purple})`,
            display:"flex", alignItems:"center", justifyContent:"center",
            fontSize:11, fontWeight:800, color:"#fff",
          }}>G</div>
          <span style={{fontWeight:700, fontSize:13, letterSpacing:"-0.02em"}}>PAW Governance</span>
          <span style={{color:C.muted, fontSize:11, borderLeft:`1px solid ${C.border}`, paddingLeft:10}}>
            Book Registry
          </span>
        </div>
        <div style={{flex:1}}/>
        {[
          [myBooks.length,     "private", C.pink],
          [sharedBooks.length, "shared",  C.blue],
          [allTabs.length,     "pages",   C.muted],
        ].map(([v,l,c]) => (
          <div key={l} style={{display:"flex", gap:4, alignItems:"baseline"}}>
            <span style={{fontFamily:"'DM Mono',monospace", fontSize:13, fontWeight:600, color:c}}>{v}</span>
            <span style={{fontSize:11, color:C.muted}}>{l}</span>
          </div>
        ))}
        <div style={{
          display:"flex", alignItems:"center", gap:5,
          background:C.card, border:`1px solid ${C.border}`,
          borderRadius:10, padding:"2px 8px", fontSize:10.5,
        }}>
          <span style={{color:C.teal, fontSize:7}}>●</span>
          <span style={{color:C.muted}}>192.168.1.178 · v12.5.5</span>
        </div>
      </div>

      {/* Body */}
      <div style={{display:"flex", flex:1, overflow:"hidden"}}>

        {/* Sidebar */}
        <div style={{
          width:238, flexShrink:0, borderRight:`1px solid ${C.border}`,
          display:"flex", flexDirection:"column", background:C.surface,
        }}>
          {/* Search */}
          <div style={{padding:"8px 8px 6px", borderBottom:`1px solid ${C.border}`}}>
            <div style={{
              display:"flex", alignItems:"center", gap:6,
              background:C.card, border:`1px solid ${C.border}`,
              borderRadius:6, padding:"5px 8px",
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <circle cx="5.5" cy="5.5" r="3.5" stroke={C.muted} strokeWidth="1.1"/>
                <line x1="8.5" y1="8.5" x2="11" y2="11" stroke={C.muted} strokeWidth="1.1" strokeLinecap="round"/>
              </svg>
              <input
                placeholder="Search…" value={search}
                onChange={e => setSearch(e.target.value)}
                style={{background:"none", border:"none", outline:"none", color:C.text, fontSize:12, width:"100%"}}
              />
              {search && (
                <span onClick={() => setSearch("")}
                  style={{color:C.muted, cursor:"pointer", fontSize:14, lineHeight:1}}>×</span>
              )}
            </div>
          </div>

          {/* Tree */}
          <div style={{flex:1, overflowY:"auto", padding:"5px 5px"}}>
            {search.trim()
              ? <SearchResults query={search} onSelect={handleSelect}/>
              : TREE.map(node => (
                  <TreeNode key={node.id} node={node} depth={0}
                    selectedId={selected?.id} onSelect={handleSelect}
                    openIds={openIds} toggleOpen={toggleOpen}/>
                ))
            }
          </div>

          {/* User footer */}
          <div style={{
            borderTop:`1px solid ${C.border}`, padding:"8px 10px",
            display:"flex", alignItems:"center", gap:8,
          }}>
            <Avatar userId={ME} size={22}/>
            <div style={{minWidth:0}}>
              <div style={{fontSize:11, color:C.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>
                {USERS[ME]?.name}
              </div>
              <div style={{fontSize:10, color:C.muted}}>{USERS[ME]?.role}</div>
            </div>
          </div>
        </div>

        {/* Detail */}
        <div style={{flex:1, background:C.bg, overflow:"hidden"}}>
          <DetailPanel node={selected} key={selected?.id}/>
        </div>
      </div>
    </div>
  );
}
