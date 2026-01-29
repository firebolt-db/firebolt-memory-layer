import React, { useState, useEffect, useCallback } from 'react'
import { 
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from 'recharts'

// API endpoint for stats (via HTTP bridge)
const API_BASE = 'http://localhost:8082/api'

// Mock data for initial render (before API connected)
const MOCK_STATS = {
  uptime_seconds: 3600,
  collection_start: new Date().toISOString(),
  time_window_minutes: 60,
  services: {
    ollama: {
      calls_in_window: 45,
      errors_in_window: 2,
      avg_latency_ms: 234.5,
      p95_latency_ms: 890.2,
      total_calls: 1234,
      total_errors: 15,
      tokens_in_window: 12500,
      tokens_out_window: 8900,
      by_operation: {
        classify: { count: 20, avg_latency_ms: 245.3 },
        summarize: { count: 15, avg_latency_ms: 312.1 },
        extract_entities: { count: 10, avg_latency_ms: 189.7 },
      }
    },
    firebolt: {
      calls_in_window: 120,
      errors_in_window: 0,
      avg_latency_ms: 45.2,
      p95_latency_ms: 125.8,
      total_calls: 5678,
      total_errors: 3,
      by_operation: {
        select: { count: 80, avg_latency_ms: 42.1 },
        insert: { count: 30, avg_latency_ms: 51.3 },
        update: { count: 10, avg_latency_ms: 48.9 },
      }
    },
    embedding: {
      calls_in_window: 35,
      errors_in_window: 0,
      avg_latency_ms: 156.7,
      p95_latency_ms: 289.4,
      total_calls: 890,
      total_errors: 1,
    }
  },
  memory: {
    long_term_memories: 156,
    active_sessions: 3,
    working_memory_items: 24,
    working_memory_tokens: 4500,
    access_log_entries: 450,
    by_category: {
      episodic: 45,
      semantic: 68,
      procedural: 28,
      preference: 15
    },
    top_accessed: [
      { memory_id: 'abc123...', category: 'semantic', access_count: 34, importance: 0.9 },
      { memory_id: 'def456...', category: 'procedural', access_count: 28, importance: 0.85 },
    ]
  }
}

// Color palette
const COLORS = {
  fire: '#F72A30',
  cyan: '#F72A30',
  purple: '#AC2422',
  green: '#FF4848',
  yellow: '#ffd60a',
}

const CATEGORY_COLORS = {
  episodic: COLORS.cyan,
  semantic: COLORS.fire,
  procedural: COLORS.purple,
  preference: COLORS.green,
}

// Stat Card Component
function StatCard({ title, value, subtitle, icon, color = 'fire', delay = 0 }) {
  return (
    <div 
      className="stat-card animate-slide-up" 
      style={{ 
        animationDelay: `${delay}ms`,
        '--accent-color': COLORS[color] || COLORS.fire
      }}
    >
      <div className="stat-icon">{icon}</div>
      <div className="stat-content">
        <div className="stat-value">{value}</div>
        <div className="stat-title">{title}</div>
        {subtitle && <div className="stat-subtitle">{subtitle}</div>}
      </div>
    </div>
  )
}

// Service descriptions and config info
const SERVICE_INFO = {
  ollama: {
    title: "LLM Classification",
    description: "Auto-classifies memories, extracts entities, detects query intent",
    operations: ["classify", "summarize", "extract_entities", "detect_intent"],
    icon: "🦙",
  },
  firebolt: {
    title: "Data Storage",
    description: "Stores memories, embeddings, sessions, and access logs",
    operations: ["select", "insert", "update"],
    icon: "🔥",
  },
  embedding: {
    title: "Vector Embeddings", 
    description: "Generates 768-dim vectors for semantic similarity search",
    operations: ["generate"],
    icon: "🔢",
  }
}

// Data Flow Diagram Component with SVG-based connections
function DataFlowDiagram({ config, delay = 0 }) {
  const ollamaHost = config?.ollama?.host || 'localhost:11434'
  const fireboltLocation = config?.brain_location === 'local' ? 'Local Core' : 'Cloud'
  const fireboltUrl = config?.firebolt?.use_core 
    ? config?.firebolt?.core_url 
    : config?.firebolt?.account_name

  // SVG dimensions for the flow diagram
  const svgWidth = 1400
  const svgHeight = 750
  
  // Node positions (centered coordinates) - shifted left to make room for legend
  const horizontalShift = -100  // Shift all boxes 100px left
  
  const cursorX = svgWidth / 2 + horizontalShift
  const cursorY = 100
  
  const fmlX = svgWidth / 2 + horizontalShift
  const fmlY = 320
  
  // Firebolt MCP Server (separate from FML, on right side)
  const fireboltMcpX = 1020 + horizontalShift  // Balanced spacing with Ollama (was 1100)
  const fireboltMcpY = 320
  
  const ollamaX = 380 + horizontalShift  // Moved closer to Embeddings (was 200)
  const ollamaY = 580
  
  const embedX = svgWidth / 2 + horizontalShift
  const embedY = 580
  
  const fireboltX = 1020 + horizontalShift  // Balanced spacing with Ollama (was 1100)
  const fireboltY = 580
  
  // Node dimensions (increased for better text spacing)
  const nodeWidth = 220
  const nodeHeight = 140
  
  // Offset for separating arrows (so they don't overlap)
  const arrowOffset = 25
  
  // Calculate connection points (using left/right sides to avoid labels)
  // Cursor bottom: separate points for request and response
  const cursorBottomLeft = { x: cursorX - arrowOffset, y: cursorY + nodeHeight / 2 }
  const cursorBottomRight = { x: cursorX + arrowOffset, y: cursorY + nodeHeight / 2 }
  const cursorBottomCenter = { x: cursorX, y: cursorY + nodeHeight / 2 }
  
  // Cursor right side: for Firebolt MCP connections (separated vertically)
  const cursorRightOut = { x: cursorX + nodeWidth / 2, y: cursorY - arrowOffset }  // Request (above)
  const cursorRightIn = { x: cursorX + nodeWidth / 2, y: cursorY + arrowOffset }   // Response (below)
  
  // Firebolt MCP Server connection points
  const fireboltMcpTopLeft = { x: fireboltMcpX - arrowOffset, y: fireboltMcpY - nodeHeight / 2 }
  const fireboltMcpTopRight = { x: fireboltMcpX + arrowOffset, y: fireboltMcpY - nodeHeight / 2 }
  const fireboltMcpBottomLeft = { x: fireboltMcpX - arrowOffset, y: fireboltMcpY + nodeHeight / 2 }
  const fireboltMcpBottomRight = { x: fireboltMcpX + arrowOffset, y: fireboltMcpY + nodeHeight / 2 }
  const fireboltMcpLeft = { x: fireboltMcpX - nodeWidth / 2, y: fireboltMcpY }
  const fireboltMcpRight = { x: fireboltMcpX + nodeWidth / 2, y: fireboltMcpY }
  
  // FML top: separate points for request in and response out
  const fmlTopLeft = { x: fmlX - arrowOffset, y: fmlY - nodeHeight / 2 }
  const fmlTopRight = { x: fmlX + arrowOffset, y: fmlY - nodeHeight / 2 }
  
  // FML left side: request out (slightly above center), response in (slightly below center)
  const fmlLeftOut = { x: fmlX - nodeWidth / 2, y: fmlY - arrowOffset }
  const fmlLeftIn = { x: fmlX - nodeWidth / 2, y: fmlY + arrowOffset }
  
  // FML right side: request out (slightly above center), response in (slightly below center)
  const fmlRightOut = { x: fmlX + nodeWidth / 2, y: fmlY - arrowOffset }
  const fmlRightIn = { x: fmlX + nodeWidth / 2, y: fmlY + arrowOffset }
  
  // FML bottom: separate points for Embeddings connections (left and right)
  const fmlBottomLeft = { x: fmlX - arrowOffset, y: fmlY + nodeHeight / 2 }
  const fmlBottomRight = { x: fmlX + arrowOffset, y: fmlY + nodeHeight / 2 }
  const fmlBottom = { x: fmlX, y: fmlY + nodeHeight / 2 }
  
  // Ollama right side: request in (slightly above), response out (slightly below)
  const ollamaRightIn = { x: ollamaX + nodeWidth / 2, y: ollamaY - arrowOffset }
  const ollamaRightOut = { x: ollamaX + nodeWidth / 2, y: ollamaY + arrowOffset }
  
  // Embeddings top: request in (left of label), response out (right of label) - separated to avoid label
  const embedTopIn = { x: embedX - arrowOffset * 3.5, y: embedY - nodeHeight / 2 }
  const embedTopOut = { x: embedX + arrowOffset * 3.5, y: embedY - nodeHeight / 2 }
  
  // Firebolt left side: request in (slightly above), response out (slightly below) - mirrors Ollama pattern
  const fireboltLeftIn = { x: fireboltX - nodeWidth / 2, y: fireboltY - arrowOffset }
  const fireboltLeftOut = { x: fireboltX - nodeWidth / 2, y: fireboltY + arrowOffset }
  
  // Firebolt Core top (for Firebolt MCP Server connection) - separated points
  const fireboltCoreTopLeft = { x: fireboltX - arrowOffset, y: fireboltY - nodeHeight / 2 }
  const fireboltCoreTopRight = { x: fireboltX + arrowOffset, y: fireboltY - nodeHeight / 2 }

  return (
    <div className="dataflow-section animate-slide-up" style={{ animationDelay: `${delay}ms` }}>
      <h2 className="section-title">Data Flow Architecture</h2>
      <div className="dataflow-container">
        {/* FML Data Flow Steps Legend (Left) */}
        <div className="flow-steps-legend">
          <div className="legend-title">FML Memory Flow (Sequential)</div>
          <div className="legend-steps">
            <div className="legend-step"><span className="step-num request">1</span> Cursor → FML (Context Request)</div>
            <div className="legend-step"><span className="step-num request">2</span> FML → Ollama (Detect Intent)</div>
            <div className="legend-step"><span className="step-num response">3</span> Ollama → FML (Intent)</div>
            <div className="legend-step"><span className="step-num request">4</span> FML → Ollama Embeddings (Vectorize)</div>
            <div className="legend-step"><span className="step-num response">5</span> Ollama Embeddings → FML (Vector)</div>
            <div className="legend-step"><span className="step-num request">6</span> FML → Firebolt (Search)</div>
            <div className="legend-step"><span className="step-num response">7</span> Firebolt → FML (Results)</div>
            <div className="legend-step"><span className="step-num response">8</span> FML → Cursor (Context)</div>
          </div>
        </div>
        
        {/* Firebolt MCP Flow Legend (Right) */}
        <div className="flow-steps-legend-right">
          <div className="legend-title">Firebolt MCP Flow (Parallel)</div>
          <div className="legend-subtitle">Direct SQL Access - Independent of FML</div>
          <div className="legend-description">
            Cursor uses this for ad-hoc queries, schema exploration, debugging, 
            and raw data access without AI overhead. Fast passthrough (~100ms vs 6s).
          </div>
          <div className="legend-steps">
            <div className="legend-step"><span className="step-num mcp">A</span> Cursor → Firebolt MCP (SQL)</div>
            <div className="legend-step"><span className="step-num mcp">B</span> Firebolt MCP → Core (Execute)</div>
            <div className="legend-step"><span className="step-num mcp">C</span> Core → Firebolt MCP (Results)</div>
            <div className="legend-step"><span className="step-num mcp">D</span> Firebolt MCP → Cursor (Data)</div>
          </div>
          <div className="legend-use-cases">
            <div className="use-case-title">Use Cases:</div>
            <div className="use-case">• List tables & schemas</div>
            <div className="use-case">• Debug SQL queries</div>
            <div className="use-case">• Analyze raw data</div>
            <div className="use-case">• Export/inspect memories</div>
          </div>
        </div>
        
        <svg 
          className="flow-svg"
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            {/* Gradient for request flow */}
            <linearGradient id="requestGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#F72A30" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#F72A30" stopOpacity="0.4" />
            </linearGradient>
            
            {/* Gradient for response flow */}
            <linearGradient id="responseGradient" x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" stopColor="#FF4848" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#FF4848" stopOpacity="0.4" />
            </linearGradient>
            
            {/* Arrow marker for requests */}
            <marker
              id="arrowRequest"
              markerWidth="12"
              markerHeight="12"
              refX="10"
              refY="6"
              orient="auto"
              markerUnits="userSpaceOnUse"
              viewBox="0 0 12 12"
            >
              <path d="M0,0 L0,12 L12,6 z" fill="#F72A30" stroke="#F72A30" strokeWidth="0.5" />
            </marker>
            
            {/* Arrow marker for responses */}
            <marker
              id="arrowResponse"
              markerWidth="12"
              markerHeight="12"
              refX="10"
              refY="6"
              orient="auto"
              markerUnits="userSpaceOnUse"
              viewBox="0 0 12 12"
            >
              <path d="M0,0 L0,12 L12,6 z" fill="#FF4848" stroke="#FF4848" strokeWidth="0.5" />
            </marker>
            
            {/* Glow filter for animated packets */}
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          
          {/* REQUEST FLOWS (downward, cyan) */}
          
          {/* Cursor → Firebolt MCP Server (right side to top right, straight line) */}
          <path
            d={`M ${cursorRightOut.x} ${cursorRightOut.y} L ${fireboltMcpTopRight.x} ${fireboltMcpTopRight.y}`}
            stroke="#F72A30"
            strokeWidth="2.5"
            fill="none"
            markerEnd="url(#arrowRequest)"
            className="flow-path request-flow"
            opacity="0.7"
          />
          {/* Step label: A - Cursor → Firebolt MCP (SQL Query) */}
          <text
            x={(cursorRightOut.x + fireboltMcpTopRight.x) / 2 + 20}
            y={(cursorRightOut.y + fireboltMcpTopRight.y) / 2 + 10}
            fill="#AC2422"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
            opacity="0.9"
          >
            A
          </text>
          
          {/* Firebolt MCP Server → Firebolt Core (bottom left to top left, separated) */}
          <path
            d={`M ${fireboltMcpBottomLeft.x} ${fireboltMcpBottomLeft.y} L ${fireboltCoreTopLeft.x} ${fireboltCoreTopLeft.y}`}
            stroke="#F72A30"
            strokeWidth="2.5"
            fill="none"
            markerEnd="url(#arrowRequest)"
            className="flow-path request-flow"
            opacity="0.7"
          />
          {/* Step label: B - Firebolt MCP → Core (Execute) */}
          <text
            x={(fireboltMcpBottomLeft.x + fireboltCoreTopLeft.x) / 2 - 20}
            y={(fireboltMcpBottomLeft.y + fireboltCoreTopLeft.y) / 2}
            fill="#AC2422"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
            opacity="0.9"
          >
            B
          </text>
          
          {/* Firebolt Core → Firebolt MCP Server (top right to bottom right, separated) */}
          <path
            d={`M ${fireboltCoreTopRight.x} ${fireboltCoreTopRight.y} L ${fireboltMcpBottomRight.x} ${fireboltMcpBottomRight.y}`}
            stroke="#FF4848"
            strokeWidth="2.5"
            fill="none"
            markerEnd="url(#arrowResponse)"
            className="flow-path response-flow"
            opacity="0.7"
            strokeDasharray="5,5"
          />
          {/* Step label: C - Core → Firebolt MCP (Results) */}
          <text
            x={(fireboltCoreTopRight.x + fireboltMcpBottomRight.x) / 2 + 20}
            y={(fireboltCoreTopRight.y + fireboltMcpBottomRight.y) / 2}
            fill="#AC2422"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
            opacity="0.9"
          >
            C
          </text>
          
          {/* Firebolt MCP Server → Cursor (top left to right side below, straight line) */}
          <path
            d={`M ${fireboltMcpTopLeft.x} ${fireboltMcpTopLeft.y} L ${cursorRightIn.x} ${cursorRightIn.y}`}
            stroke="#FF4848"
            strokeWidth="2.5"
            fill="none"
            markerEnd="url(#arrowResponse)"
            className="flow-path response-flow"
            opacity="0.7"
            strokeDasharray="5,5"
          />
          {/* Step label: D - Firebolt MCP → Cursor (Data) */}
          <text
            x={(fireboltMcpTopLeft.x + cursorRightIn.x) / 2 - 20}
            y={(fireboltMcpTopLeft.y + cursorRightIn.y) / 2 - 10}
            fill="#AC2422"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
            opacity="0.9"
          >
            D
          </text>
          
          {/* Cursor → FML (left side to left side, separated) */}
          <path
            d={`M ${cursorBottomLeft.x} ${cursorBottomLeft.y} L ${fmlTopLeft.x} ${fmlTopLeft.y}`}
            stroke="url(#requestGradient)"
            strokeWidth="3"
            fill="none"
            markerEnd="url(#arrowRequest)"
            className="flow-path request-flow"
          />
          {/* Step label: 1 */}
          <text
            x={(cursorBottomLeft.x + fmlTopLeft.x) / 2}
            y={(cursorBottomLeft.y + fmlTopLeft.y) / 2 - 15}
            fill="#F72A30"
            fontSize="14"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
          >
            1
          </text>
          {/* Animated packet on Cursor → FML */}
          <circle
            r="6"
            fill="#F72A30"
            filter="url(#glow)"
            className="data-packet-svg packet-1"
          >
            <animateMotion
              dur="2s"
              repeatCount="indefinite"
              path={`M ${cursorBottomLeft.x} ${cursorBottomLeft.y} L ${fmlTopLeft.x} ${fmlTopLeft.y}`}
            />
          </circle>
          
          {/* FML → Ollama (left side to right side, separated) */}
          <path
            d={`M ${fmlLeftOut.x} ${fmlLeftOut.y} Q ${(fmlLeftOut.x + ollamaRightIn.x) / 2} ${fmlLeftOut.y + 120} ${ollamaRightIn.x} ${ollamaRightIn.y}`}
            stroke="url(#requestGradient)"
            strokeWidth="2.5"
            fill="none"
            markerEnd="url(#arrowRequest)"
            className="flow-path request-flow"
            opacity="0.7"
          />
          {/* Step label: 2 - FML → Ollama (Detect Intent) */}
          <text
            x={(fmlLeftOut.x + ollamaRightIn.x) / 2 - 25}
            y={(fmlLeftOut.y + ollamaRightIn.y) / 2 + 50}
            fill="#F72A30"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
            opacity="0.9"
          >
            2
          </text>
          <circle
            r="5"
            fill="#F72A30"
            filter="url(#glow)"
            className="data-packet-svg packet-2"
          >
            <animateMotion
              dur="2.5s"
              repeatCount="indefinite"
              begin="0.3s"
              path={`M ${fmlLeftOut.x} ${fmlLeftOut.y} Q ${(fmlLeftOut.x + ollamaRightIn.x) / 2} ${fmlLeftOut.y + 120} ${ollamaRightIn.x} ${ollamaRightIn.y}`}
            />
          </circle>
          
          {/* FML → Embeddings (bottom left to top left, straight line) */}
          <path
            d={`M ${fmlBottomLeft.x} ${fmlBottomLeft.y} L ${embedTopIn.x} ${embedTopIn.y}`}
            stroke="url(#requestGradient)"
            strokeWidth="2.5"
            fill="none"
            markerEnd="url(#arrowRequest)"
            className="flow-path request-flow"
            opacity="0.7"
          />
          {/* Step label: 4 - FML → Embeddings (Vectorize) */}
          <text
            x={(fmlBottomLeft.x + embedTopIn.x) / 2 - 25}
            y={(fmlBottomLeft.y + embedTopIn.y) / 2 - 10}
            fill="#F72A30"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
            opacity="0.9"
          >
            4
          </text>
          <circle
            r="5"
            fill="#F72A30"
            filter="url(#glow)"
            className="data-packet-svg packet-3"
          >
            <animateMotion
              dur="2.2s"
              repeatCount="indefinite"
              begin="0.6s"
              path={`M ${fmlBottomLeft.x} ${fmlBottomLeft.y} L ${embedTopIn.x} ${embedTopIn.y}`}
            />
          </circle>
          
          {/* FML → Firebolt (right side to left side, mirrors Ollama pattern) */}
          <path
            d={`M ${fmlRightOut.x} ${fmlRightOut.y} Q ${(fmlRightOut.x + fireboltLeftIn.x) / 2} ${fmlRightOut.y + 120} ${fireboltLeftIn.x} ${fireboltLeftIn.y}`}
            stroke="url(#requestGradient)"
            strokeWidth="2.5"
            fill="none"
            markerEnd="url(#arrowRequest)"
            className="flow-path request-flow"
            opacity="0.7"
          />
          {/* Step label: 6 - FML → Firebolt (Search Memories) */}
          <text
            x={(fmlRightOut.x + fireboltLeftIn.x) / 2 + 25}
            y={(fmlRightOut.y + fireboltLeftIn.y) / 2 + 50}
            fill="#F72A30"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
            opacity="0.9"
          >
            6
          </text>
          <circle
            r="5"
            fill="#F72A30"
            filter="url(#glow)"
            className="data-packet-svg packet-4"
          >
            <animateMotion
              dur="2.3s"
              repeatCount="indefinite"
              begin="0.9s"
              path={`M ${fmlRightOut.x} ${fmlRightOut.y} Q ${(fmlRightOut.x + fireboltLeftIn.x) / 2} ${fmlRightOut.y + 120} ${fireboltLeftIn.x} ${fireboltLeftIn.y}`}
            />
          </circle>
          
          {/* RESPONSE FLOWS (upward, green) */}
          
          {/* Ollama → FML (right side to left side, separated) */}
          <path
            d={`M ${ollamaRightOut.x} ${ollamaRightOut.y} Q ${(ollamaRightOut.x + fmlLeftIn.x) / 2} ${ollamaRightOut.y - 120} ${fmlLeftIn.x} ${fmlLeftIn.y}`}
            stroke="url(#responseGradient)"
            strokeWidth="2.5"
            fill="none"
            markerEnd="url(#arrowResponse)"
            className="flow-path response-flow"
            opacity="0.7"
            strokeDasharray="5,5"
          />
          {/* Step label: 3 - Ollama → FML (Intent Response) */}
          <text
            x={(ollamaRightOut.x + fmlLeftIn.x) / 2 + 10}
            y={(ollamaRightOut.y + fmlLeftIn.y) / 2 - 20}
            fill="#FF4848"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
            opacity="0.9"
          >
            3
          </text>
          <circle
            r="5"
            fill="#FF4848"
            filter="url(#glow)"
            className="data-packet-svg packet-5"
          >
            <animateMotion
              dur="2.5s"
              repeatCount="indefinite"
              begin="1.2s"
              path={`M ${ollamaRightOut.x} ${ollamaRightOut.y} Q ${(ollamaRightOut.x + fmlLeftIn.x) / 2} ${ollamaRightOut.y - 120} ${fmlLeftIn.x} ${fmlLeftIn.y}`}
            />
          </circle>
          
          {/* Embeddings → FML (top right to bottom right, straight line) */}
          <path
            d={`M ${embedTopOut.x} ${embedTopOut.y} L ${fmlBottomRight.x} ${fmlBottomRight.y}`}
            stroke="url(#responseGradient)"
            strokeWidth="2.5"
            fill="none"
            markerEnd="url(#arrowResponse)"
            className="flow-path response-flow"
            opacity="0.7"
            strokeDasharray="5,5"
          />
          {/* Step label: 5 - Embeddings → FML (Vector Response) */}
          <text
            x={(embedTopOut.x + fmlBottomRight.x) / 2 + 25}
            y={(embedTopOut.y + fmlBottomRight.y) / 2 - 10}
            fill="#FF4848"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
            opacity="0.9"
          >
            5
          </text>
          <circle
            r="5"
            fill="#FF4848"
            filter="url(#glow)"
            className="data-packet-svg packet-6"
          >
            <animateMotion
              dur="2.2s"
              repeatCount="indefinite"
              begin="1.5s"
              path={`M ${embedTopOut.x} ${embedTopOut.y} L ${fmlBottomRight.x} ${fmlBottomRight.y}`}
            />
          </circle>
          
          {/* Firebolt → FML (left side to right side, mirrors Ollama pattern) */}
          <path
            d={`M ${fireboltLeftOut.x} ${fireboltLeftOut.y} Q ${(fireboltLeftOut.x + fmlRightIn.x) / 2} ${fireboltLeftOut.y - 120} ${fmlRightIn.x} ${fmlRightIn.y}`}
            stroke="url(#responseGradient)"
            strokeWidth="2.5"
            fill="none"
            markerEnd="url(#arrowResponse)"
            className="flow-path response-flow"
            opacity="0.7"
            strokeDasharray="5,5"
          />
          {/* Step label: 7 - Firebolt → FML RESPONSE */}
          <text
            x={(fireboltLeftOut.x + fmlRightIn.x) / 2 - 10}
            y={(fireboltLeftOut.y + fmlRightIn.y) / 2 - 20}
            fill="#FF4848"
            fontSize="12"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
            opacity="0.9"
          >
            7
          </text>
          <circle
            r="5"
            fill="#FF4848"
            filter="url(#glow)"
            className="data-packet-svg packet-7"
          >
            <animateMotion
              dur="2.3s"
              repeatCount="indefinite"
              begin="1.8s"
              path={`M ${fireboltLeftOut.x} ${fireboltLeftOut.y} Q ${(fireboltLeftOut.x + fmlRightIn.x) / 2} ${fireboltLeftOut.y - 120} ${fmlRightIn.x} ${fmlRightIn.y}`}
            />
          </circle>
          
          {/* FML → Cursor (right side to right side, separated) */}
          <path
            d={`M ${fmlTopRight.x} ${fmlTopRight.y} L ${cursorBottomRight.x} ${cursorBottomRight.y}`}
            stroke="url(#responseGradient)"
            strokeWidth="3"
            fill="none"
            markerEnd="url(#arrowResponse)"
            className="flow-path response-flow"
            strokeDasharray="6,4"
          />
          {/* Step label: 8 */}
          <text
            x={(fmlTopRight.x + cursorBottomRight.x) / 2}
            y={(fmlTopRight.y + cursorBottomRight.y) / 2 - 15}
            fill="#FF4848"
            fontSize="14"
            fontWeight="700"
            textAnchor="middle"
            className="flow-step-label"
          >
            8
          </text>
          <circle
            r="6"
            fill="#FF4848"
            filter="url(#glow)"
            className="data-packet-svg packet-8"
          >
            <animateMotion
              dur="2s"
              repeatCount="indefinite"
              begin="2.1s"
              path={`M ${fmlTopRight.x} ${fmlTopRight.y} L ${cursorBottomRight.x} ${cursorBottomRight.y}`}
            />
          </circle>
        </svg>
        
        {/* Node overlays (positioned absolutely over SVG) */}
        <div className="flow-nodes-overlay">
          {/* Cursor Node */}
          <div 
            className="flow-node cursor-node"
            style={{
              left: `${(cursorX / svgWidth) * 100}%`,
              top: `${(cursorY / svgHeight) * 100}%`,
              width: `${(nodeWidth / svgWidth) * 100}%`,
              height: `${(nodeHeight / svgHeight) * 100}%`,
              transform: 'translate(-50%, -50%)',
              marginLeft: 0,
              marginTop: 0
            }}
          >
            <div className="node-icon">🖥️</div>
            <div className="node-label">Cursor IDE</div>
            <div className="node-action">"How do I connect to Firebolt?"</div>
          </div>
          
          {/* Firebolt MCP Server Node */}
          <div 
            className="flow-node firebolt-mcp-node"
            style={{
              left: `${(fireboltMcpX / svgWidth) * 100}%`,
              top: `${(fireboltMcpY / svgHeight) * 100}%`,
              width: `${(nodeWidth / svgWidth) * 100}%`,
              height: `${(nodeHeight / svgHeight) * 100}%`,
              transform: 'translate(-50%, -50%)'
            }}
          >
            <div className="node-icon">🐳</div>
            <div className="node-label">Firebolt MCP</div>
            <div className="node-action">Direct Queries</div>
            <div className="node-url">localhost:8080/sse</div>
          </div>
          
          {/* FML Node */}
          <div 
            className="flow-node fml-node"
            style={{
              left: `${(fmlX / svgWidth) * 100}%`,
              top: `${(fmlY / svgHeight) * 100}%`,
              width: `${(nodeWidth / svgWidth) * 100}%`,
              height: `${(nodeHeight / svgHeight) * 100}%`,
              transform: 'translate(-50%, -50%)'
            }}
          >
            <div className="node-icon">🧠</div>
            <div className="node-label">FML Server</div>
            <div className="node-action">Orchestrates & Aggregates</div>
          </div>
          
          {/* Ollama Node */}
          <div 
            className="flow-node ollama-node"
            style={{
              left: `${(ollamaX / svgWidth) * 100}%`,
              top: `${(ollamaY / svgHeight) * 100}%`,
              width: `${(nodeWidth / svgWidth) * 100}%`,
              height: `${(nodeHeight / svgHeight) * 100}%`,
              transform: 'translate(-50%, -50%)'
            }}
          >
            <div className="node-icon">🦙</div>
            <div className="node-label">Ollama LLM</div>
            <div className="node-action">Classify Intent</div>
            <div className="node-url">{ollamaHost}</div>
          </div>
          
          {/* Embeddings Node */}
          <div 
            className="flow-node embed-node"
            style={{
              left: `${(embedX / svgWidth) * 100}%`,
              top: `${(embedY / svgHeight) * 100}%`,
              width: `${(nodeWidth / svgWidth) * 100}%`,
              height: `${(nodeHeight / svgHeight) * 100}%`,
              transform: 'translate(-50%, -50%)'
            }}
          >
            <div className="node-icon">🔢</div>
            <div className="node-label">Ollama Embeddings</div>
            <div className="node-action">Generate Vector</div>
            <div className="node-url">{ollamaHost}</div>
          </div>
          
          {/* Firebolt Node */}
          <div 
            className="flow-node firebolt-node"
            style={{
              left: `${(fireboltX / svgWidth) * 100}%`,
              top: `${(fireboltY / svgHeight) * 100}%`,
              width: `${(nodeWidth / svgWidth) * 100}%`,
              height: `${(nodeHeight / svgHeight) * 100}%`,
              transform: 'translate(-50%, -50%)'
            }}
          >
            <div className="node-icon">🔥</div>
            <div className="node-label">Firebolt {fireboltLocation}</div>
            <div className="node-action">Vector Search</div>
            <div className="node-url">{fireboltUrl}</div>
          </div>
        </div>
      </div>
      
      <div className="flow-legend">
        <div className="legend-item">
          <span className="legend-line request"></span>
          <span>Request Flow (Down)</span>
        </div>
        <div className="legend-item">
          <span className="legend-line response"></span>
          <span>Response Flow (Up)</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot local"></span>
          <span>All Local Services</span>
        </div>
      </div>
    </div>
  )
}

// Service Panel Component
function ServicePanel({ name, data, config, delay = 0 }) {
  const info = SERVICE_INFO[name] || { title: name, description: '', icon: '📦' }
  const statusColor = data.errors_in_window > 0 ? COLORS.yellow : COLORS.green
  
  // Determine if service is local or cloud
  let location = 'local'
  let locationUrl = ''
  if (name === 'ollama' || name === 'embedding') {
    locationUrl = config?.ollama?.host || 'localhost:11434'
  } else if (name === 'firebolt') {
    location = config?.firebolt?.use_core ? 'local' : 'cloud'
    locationUrl = config?.firebolt?.use_core 
      ? config?.firebolt?.core_url 
      : config?.firebolt?.account_name
  }
  
  const operationData = data.by_operation 
    ? Object.entries(data.by_operation).map(([op, stats]) => ({
        name: op,
        count: stats.count,
        latency: Math.round(stats.avg_latency_ms),
      }))
    : []

  return (
    <div className="service-panel animate-slide-up" style={{ animationDelay: `${delay}ms` }}>
      <div className="service-header">
        <div className="service-name">
          <span className="service-dot" style={{ background: statusColor }} />
          <span className="service-icon">{info.icon}</span>
          {info.title}
        </div>
        <div className="service-status">
          {data.calls_in_window || 0} calls/hr
        </div>
      </div>
      <div className="service-description">{info.description}</div>
      <div className="service-location">
        <span className={`location-badge ${location}`}>
          {location === 'local' ? '🏠 Local' : '☁️ Cloud'}
        </span>
        <span className="location-url">{locationUrl}</span>
      </div>
      
      <div className="service-metrics">
        <div className="metric">
          <span className="metric-label">Avg Latency</span>
          <span className="metric-value">{data.avg_latency_ms?.toFixed(1) || 0}ms</span>
        </div>
        <div className="metric">
          <span className="metric-label">P95 Latency</span>
          <span className="metric-value">{data.p95_latency_ms?.toFixed(1) || 0}ms</span>
        </div>
        <div className="metric">
          <span className="metric-label">All-Time Calls</span>
          <span className="metric-value">{data.total_calls?.toLocaleString() || 0}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Errors</span>
          <span className="metric-value" style={{ color: data.total_errors > 0 ? COLORS.yellow : 'inherit' }}>
            {data.total_errors || 0}
          </span>
        </div>
      </div>

      {name === 'ollama' && (
        <div className="token-stats">
          <div className="token-stat">
            <span className="token-label">Tokens In</span>
            <span className="token-value">{(data.tokens_in_window || 0).toLocaleString()}</span>
          </div>
          <div className="token-stat">
            <span className="token-label">Tokens Out</span>
            <span className="token-value">{(data.tokens_out_window || 0).toLocaleString()}</span>
          </div>
        </div>
      )}

      {operationData.length > 0 && (
        <div className="operation-chart">
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={operationData} layout="vertical">
              <XAxis type="number" hide />
              <YAxis 
                type="category" 
                dataKey="name" 
                width={80}
                tick={{ fill: '#8888a0', fontSize: 11 }}
              />
              <Tooltip 
                contentStyle={{ 
                  background: '#F5EBEB', 
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px'
                }}
                labelStyle={{ color: '#f0f0f5' }}
              />
              <Bar 
                dataKey="count" 
                fill={COLORS.fire}
                radius={[0, 4, 4, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

// Memory Distribution Chart
function MemoryDistribution({ data, delay = 0 }) {
  const chartData = Object.entries(data || {}).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: parseInt(value, 10) || 0,  // Convert string to number for chart
    color: CATEGORY_COLORS[name] || COLORS.fire
  }))

  return (
    <div className="chart-card animate-slide-up" style={{ animationDelay: `${delay}ms` }}>
      <h3 className="chart-title">Memory by Category</h3>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={80}
            paddingAngle={2}
            dataKey="value"
          >
            {chartData.map((entry, index) => (
              <Cell key={index} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip 
            contentStyle={{ 
              background: '#F5EBEB', 
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px'
            }}
          />
          <Legend 
            verticalAlign="bottom"
            iconType="circle"
            formatter={(value) => <span style={{ color: '#8888a0', fontSize: '12px' }}>{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

// Recent Calls Table
function RecentCalls({ calls, delay = 0 }) {
  return (
    <div className="calls-card animate-slide-up" style={{ animationDelay: `${delay}ms` }}>
      <h3 className="chart-title">Recent LLM Calls</h3>
      <div className="calls-table">
        <div className="calls-header">
          <span>Time</span>
          <span>Operation</span>
          <span>Latency</span>
          <span>Status</span>
        </div>
        {(calls || []).slice(0, 8).map((call, i) => (
          <div key={i} className="calls-row">
            <span className="call-time">
              {new Date(call.timestamp).toLocaleTimeString()}
            </span>
            <span className="call-operation">{call.operation}</span>
            <span className="call-latency">{call.latency_ms}ms</span>
            <span className={`call-status ${call.success ? 'success' : 'error'}`}>
              {call.success ? '✓' : '✗'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// Main App Component
export default function App() {
  const [stats, setStats] = useState(null)
  const [recentCalls, setRecentCalls] = useState([])
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [brainConfig, setBrainConfig] = useState(null)
  const [versionInfo, setVersionInfo] = useState(null)

  const fetchConfig = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/config`)
      if (response.ok) {
        const data = await response.json()
        setBrainConfig(data)
      }
    } catch (e) {
      // API not available
    }
  }, [])

  const fetchVersion = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/version`)
      if (response.ok) {
        const data = await response.json()
        setVersionInfo(data)
      }
    } catch (e) {
      // API not available
    }
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/stats`)
      if (response.ok) {
        const data = await response.json()
        setStats(data)
        setConnected(true)
        setLastUpdate(new Date())
      } else {
        // API returned error, use mock data for demo
        setStats(MOCK_STATS)
        setConnected(false)
      }
    } catch (e) {
      // API not available, use mock data for demo
      setStats(MOCK_STATS)
      setConnected(false)
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchCalls = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/calls/ollama`)
      if (response.ok) {
        const data = await response.json()
        setRecentCalls(data.calls || [])
      }
    } catch (e) {
      // API not available
    }
  }, [])

  useEffect(() => {
    fetchStats()
    fetchCalls()
    fetchConfig()
    fetchVersion()
    
    // Refresh every 5 seconds
    const interval = setInterval(() => {
      fetchStats()
      fetchCalls()
      fetchVersion()  // Check if server needs restart
    }, 5000)

    return () => clearInterval(interval)
  }, [fetchStats, fetchCalls, fetchConfig, fetchVersion])

  const formatUptime = (seconds) => {
    const hrs = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m`
  }

  // Show loading state on initial load
  if (loading) {
    return (
      <div className="dashboard">
        <div className="loading-container">
          <div className="loading-spinner" />
          <div className="loading-text">Connecting to FML...</div>
        </div>
        <style>{`
          .loading-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            gap: 24px;
          }
          .loading-spinner {
            width: 48px;
            height: 48px;
            border: 3px solid rgba(247, 42, 48, 0.2);
            border-top-color: #F72A30;
            border-radius: 50%;
            animation: spin 1s linear infinite;
          }
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
          .loading-text {
            font-size: 16px;
            color: var(--text-secondary);
            font-family: var(--font-mono);
          }
        `}</style>
      </div>
    )
  }

  // Safe accessor for stats (fallback to empty object structure)
  const safeStats = stats || { services: {}, memory: {} }

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <h1 className="logo">
            <span className="logo-icon">🔥</span>
            FML Dashboard
          </h1>
          <span className="logo-subtitle">Firebolt Memory Layer</span>
        </div>
        <div className="header-right">
          {brainConfig && (
            <div className={`brain-location ${brainConfig.brain_location}`}>
              <span className="brain-icon">{brainConfig.brain_location === 'local' ? '🏠' : '☁️'}</span>
              <span className="brain-label">
                {brainConfig.brain_location === 'local' ? 'Local Core' : 'Cloud'}
              </span>
              <span className="brain-detail">
                {brainConfig.brain_location === 'local' 
                  ? brainConfig.firebolt.core_url 
                  : brainConfig.firebolt.account_name}
              </span>
            </div>
          )}
          <div className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
            <span className="status-dot" />
            {connected ? 'Connected' : 'Using Demo Data'}
          </div>
          {lastUpdate && (
            <div className="last-update">
              Updated {lastUpdate.toLocaleTimeString()}
            </div>
          )}
        </div>
      </header>

      {/* Server Restart Warning Banner */}
      {versionInfo?.needs_restart && (
        <div className="restart-warning">
          <span className="warning-icon">⚠️</span>
          <div className="warning-content">
            <strong>Server Running Stale Code</strong>
            <span>The HTTP API server needs to be restarted to pick up code changes.</span>
            <span className="warning-details">
              Code modified: {new Date(versionInfo.code_modified_time).toLocaleString()} · 
              Server started: {new Date(versionInfo.server_start_time).toLocaleString()}
            </span>
          </div>
          <code className="restart-command">pkill -f "python.*http_api" && cd fml/fml-server && PYTHONPATH=. python3 -m src.http_api &</code>
        </div>
      )}

      {/* Main Content */}
      <main className="dashboard-content">
        {/* Data Flow Diagram */}
        <DataFlowDiagram config={brainConfig} delay={0} />

        {/* Stats Row */}
        <section className="stats-row">
          <StatCard 
            title="Long-term Memories" 
            value={safeStats.memory?.long_term_memories || 0}
            icon="🧠"
            color="fire"
            delay={100}
          />
          <StatCard 
            title="Session History" 
            value={safeStats.memory?.active_sessions || 0}
            icon="📋"
            color="cyan"
            delay={150}
          />
          <StatCard 
            title="Working Memory" 
            value={`${safeStats.memory?.working_memory_tokens?.toLocaleString() || 0} tokens`}
            subtitle={`${safeStats.memory?.working_memory_items || 0} items`}
            icon="📝"
            color="purple"
            delay={200}
          />
          <StatCard 
            title="Memory Data Size" 
            value={safeStats.memory?.storage?.total_uncompressed_formatted || '0 B'}
            subtitle={`Raw data size before compression · ${safeStats.memory?.storage?.total_compressed_formatted || '0 B'} actual disk usage`}
            icon="💾"
            color="green"
            delay={250}
          />
        </section>

        {/* Services Grid */}
        <section className="services-section">
          <h2 className="section-title">Service Health</h2>
          <div className="services-grid">
            <ServicePanel 
              name="ollama" 
              data={safeStats.services?.ollama || {}} 
              config={brainConfig}
              delay={300}
            />
            <ServicePanel 
              name="embedding" 
              data={safeStats.services?.embedding || {}} 
              config={brainConfig}
              delay={350}
            />
            <ServicePanel 
              name="firebolt" 
              data={safeStats.services?.firebolt || {}} 
              config={brainConfig}
              delay={400}
            />
          </div>
        </section>

        {/* Charts Row */}
        <section className="charts-section">
          <MemoryDistribution 
            data={safeStats.memory?.by_category} 
            delay={350}
          />
          <RecentCalls 
            calls={recentCalls} 
            delay={400}
          />
        </section>

        {/* Top Accessed */}
        {safeStats.memory?.top_accessed?.length > 0 && (
          <section className="top-accessed animate-slide-up" style={{ animationDelay: '450ms' }}>
            <h2 className="section-title">Most Accessed Memories</h2>
            <div className="memory-list">
              {safeStats.memory.top_accessed.map((mem, i) => (
                <div key={i} className="memory-item">
                  <div className="memory-header">
                    <span 
                      className="memory-category" 
                      style={{ background: CATEGORY_COLORS[mem.category] || COLORS.fire }}
                    >
                      {mem.category}
                    </span>
                    <span className="memory-access">{mem.access_count} accesses</span>
                    <div className="memory-importance">
                      <div 
                        className="importance-bar" 
                        style={{ width: `${mem.importance * 100}%` }}
                      />
                    </div>
                  </div>
                  <div className="memory-content">{mem.content_preview || mem.memory_id}</div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>

      <style>{`
        .dashboard {
          min-height: 100vh;
          padding: 0 24px 48px;
        }

        .dashboard-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 24px 0;
          border-bottom: 1px solid var(--border-subtle);
          margin-bottom: 32px;
        }

        .restart-warning {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 16px 20px;
          margin-bottom: 24px;
          background: linear-gradient(135deg, rgba(255, 193, 7, 0.15), rgba(255, 152, 0, 0.1));
          border: 1px solid rgba(255, 193, 7, 0.4);
          border-radius: 12px;
          animation: pulse-warning 2s ease-in-out infinite;
        }

        @keyframes pulse-warning {
          0%, 100% { box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.2); }
          50% { box-shadow: 0 0 20px 4px rgba(255, 193, 7, 0.3); }
        }

        .restart-warning .warning-icon {
          font-size: 24px;
        }

        .restart-warning .warning-content {
          display: flex;
          flex-direction: column;
          gap: 4px;
          flex: 1;
        }

        .restart-warning .warning-content strong {
          color: #ff9800;
          font-size: 14px;
        }

        .restart-warning .warning-content span {
          color: var(--text-secondary);
          font-size: 12px;
        }

        .restart-warning .warning-details {
          color: var(--text-muted);
          font-size: 11px;
        }

        .restart-warning .restart-command {
          background: rgba(0, 0, 0, 0.2);
          padding: 8px 12px;
          border-radius: 6px;
          font-size: 10px;
          color: var(--text-muted);
          max-width: 400px;
          overflow-x: auto;
          white-space: nowrap;
        }

        .header-left {
          display: flex;
          align-items: baseline;
          gap: 16px;
        }

        .logo {
          font-size: 28px;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .logo-icon {
          font-size: 32px;
        }

        .logo-subtitle {
          color: var(--text-secondary);
          font-size: 14px;
          font-weight: 400;
        }

        .header-right {
          display: flex;
          align-items: center;
          gap: 24px;
        }

        .connection-status {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          font-family: var(--font-mono);
        }

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          animation: pulse-glow 2s infinite;
        }

        .connection-status.connected .status-dot {
          background: var(--accent-green);
          box-shadow: 0 0 8px var(--accent-green);
        }

        .connection-status.disconnected .status-dot {
          background: var(--accent-yellow);
          box-shadow: 0 0 8px var(--accent-yellow);
        }

        .brain-location {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 16px;
          border-radius: 20px;
          font-size: 12px;
          font-family: var(--font-mono);
        }

        .brain-location.local {
          background: linear-gradient(135deg, rgba(255, 72, 72, 0.15), rgba(247, 42, 48, 0.1));
          border: 1px solid rgba(255, 72, 72, 0.3);
        }

        .brain-location.cloud {
          background: linear-gradient(135deg, rgba(172, 36, 34, 0.15), rgba(247, 42, 48, 0.1));
          border: 1px solid rgba(172, 36, 34, 0.3);
        }

        .brain-icon {
          font-size: 16px;
        }

        .brain-label {
          font-weight: 600;
          color: var(--text-primary);
        }

        .brain-detail {
          color: var(--text-muted);
          font-size: 10px;
        }

        .last-update {
          color: var(--text-muted);
          font-size: 12px;
        }

        .dashboard-content {
          max-width: 1400px;
          margin: 0 auto;
        }

        /* Stats Row */
        .stats-row {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 20px;
          margin-bottom: 32px;
        }

        .stat-card {
          background: var(--bg-card);
          border: 1px solid var(--border-subtle);
          border-radius: 16px;
          padding: 24px;
          display: flex;
          align-items: flex-start;
          gap: 16px;
          transition: all 0.3s ease;
          position: relative;
          overflow: hidden;
        }

        .stat-card::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 2px;
          background: var(--accent-color);
          opacity: 0.6;
        }

        .stat-card:hover {
          background: var(--bg-card-hover);
          border-color: var(--accent-color);
          transform: translateY(-2px);
          box-shadow: var(--shadow-card);
        }

        .stat-icon {
          font-size: 32px;
          opacity: 0.9;
        }

        .stat-value {
          font-size: 28px;
          font-weight: 700;
          color: var(--text-primary);
          font-family: var(--font-mono);
        }

        .stat-title {
          font-size: 13px;
          color: var(--text-secondary);
          margin-top: 4px;
        }

        .stat-subtitle {
          font-size: 11px;
          color: var(--text-muted);
          margin-top: 2px;
        }

        /* Sections */
        .section-title {
          font-size: 18px;
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: 20px;
        }

        /* Services Section */
        .services-section {
          margin-bottom: 32px;
        }

        .services-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 20px;
        }

        .service-panel {
          background: var(--bg-card);
          border: 1px solid var(--border-subtle);
          border-radius: 16px;
          padding: 20px;
        }

        /* Data Flow Diagram - SVG-based Layout */
        .dataflow-section {
          margin-bottom: 32px;
        }

        .dataflow-container {
          background: linear-gradient(135deg, rgba(247, 42, 48, 0.03), rgba(247, 42, 48, 0.03));
          border: 1px solid rgba(26, 4, 4, 0.1);
          border-radius: 16px;
          padding: 40px;
          position: relative;
          overflow: hidden;
          width: 100%;
          max-width: 1480px;
          margin: 0 auto;
          aspect-ratio: 1400 / 750;
        }

        .flow-steps-legend {
          position: absolute;
          top: 20px;
          left: 20px;
          background: rgba(255, 255, 255, 0.95);
          border: 1px solid rgba(26, 4, 4, 0.12);
          border-radius: 12px;
          padding: 16px;
          z-index: 10;
          max-width: 320px;
          backdrop-filter: blur(8px);
        }

        .flow-steps-legend .legend-title {
          font-size: 14px;
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: 12px;
          padding-bottom: 8px;
          border-bottom: 1px solid rgba(26, 4, 4, 0.1);
        }

        .flow-steps-legend .legend-steps {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .flow-steps-legend .legend-step {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 12px;
          color: var(--text-secondary);
          line-height: 1.4;
        }

        .flow-steps-legend .step-num {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 22px;
          height: 22px;
          border-radius: 50%;
          font-size: 11px;
          font-weight: 700;
          font-family: var(--font-mono);
          flex-shrink: 0;
        }

        .flow-steps-legend .step-num.request {
          background: rgba(247, 42, 48, 0.2);
          color: #F72A30;
          border: 1px solid rgba(247, 42, 48, 0.4);
        }

        .flow-steps-legend .step-num.response {
          background: rgba(255, 72, 72, 0.2);
          color: #FF4848;
          border: 1px solid rgba(255, 72, 72, 0.4);
        }

        .flow-steps-legend .step-num.mcp {
          background: rgba(172, 36, 34, 0.2);
          color: #AC2422;
          border: 1px solid rgba(172, 36, 34, 0.4);
        }

        /* Right legend for Firebolt MCP flow */
        .flow-steps-legend-right {
          position: absolute;
          top: 20px;
          right: 20px;
          background: rgba(255, 255, 255, 0.95);
          border: 1px solid rgba(172, 36, 34, 0.3);
          border-radius: 12px;
          padding: 16px;
          z-index: 10;
          max-width: 320px;
          backdrop-filter: blur(8px);
        }

        .flow-steps-legend-right .legend-title {
          font-size: 14px;
          font-weight: 600;
          color: var(--accent-purple);
          margin-bottom: 4px;
        }

        .flow-steps-legend-right .legend-subtitle {
          font-size: 11px;
          color: var(--text-muted);
          margin-bottom: 8px;
        }

        .flow-steps-legend-right .legend-description {
          font-size: 11px;
          color: var(--text-secondary);
          line-height: 1.5;
          margin-bottom: 12px;
          padding-bottom: 12px;
          border-bottom: 1px solid rgba(172, 36, 34, 0.2);
        }

        .flow-steps-legend-right .legend-steps {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .flow-steps-legend-right .legend-step {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 12px;
          color: var(--text-secondary);
          line-height: 1.4;
        }

        .flow-steps-legend-right .step-num {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 22px;
          height: 22px;
          border-radius: 50%;
          font-size: 11px;
          font-weight: 700;
          font-family: var(--font-mono);
          flex-shrink: 0;
          background: rgba(172, 36, 34, 0.2);
          color: #AC2422;
          border: 1px solid rgba(172, 36, 34, 0.4);
        }

        .flow-steps-legend-right .legend-use-cases {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid rgba(172, 36, 34, 0.2);
        }

        .flow-steps-legend-right .use-case-title {
          font-size: 11px;
          font-weight: 600;
          color: var(--accent-purple);
          margin-bottom: 8px;
        }

        .flow-steps-legend-right .use-case {
          font-size: 10px;
          color: var(--text-muted);
          line-height: 1.6;
          padding-left: 4px;
        }

        .flow-svg {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          pointer-events: none;
        }

        .flow-nodes-overlay {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          z-index: 10;
          pointer-events: none;
        }
        
        .flow-nodes-overlay .flow-node {
          pointer-events: auto;
        }

        .flow-path {
          pointer-events: none;
        }

        .request-flow {
          animation: pathGlow 2s ease-in-out infinite;
        }

        .response-flow {
          animation: pathGlow 2s ease-in-out infinite;
        }

        @keyframes pathGlow {
          0%, 100% { opacity: 0.6; }
          50% { opacity: 1; }
        }

        .data-packet-svg {
          pointer-events: none;
        }

        .flow-step-label {
          pointer-events: none;
          user-select: none;
          paint-order: stroke fill;
          stroke: rgba(0, 0, 0, 0.8);
          stroke-width: 3px;
          stroke-linejoin: round;
        }

        /* Flow Nodes - Light mode */
        .flow-node {
          background: rgba(255, 255, 255, 0.98);
          border: 2px solid rgba(26, 4, 4, 0.15);
          border-radius: 12px;
          padding: 20px 24px;
          text-align: center;
          position: absolute;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 16px rgba(26, 4, 4, 0.08);
          gap: 8px;
        }

        .flow-node.cursor-node {
          border-color: var(--accent-cyan);
          box-shadow: 0 0 20px rgba(247, 42, 48, 0.2);
        }

        .flow-node.fml-node {
          border-color: var(--accent-fire);
          box-shadow: 0 0 20px rgba(247, 42, 48, 0.2);
        }

        .flow-node.ollama-node,
        .flow-node.embed-node {
          border-color: var(--accent-green);
          box-shadow: 0 0 15px rgba(255, 72, 72, 0.15);
        }

        .flow-node.firebolt-node {
          border-color: var(--accent-fire);
          box-shadow: 0 0 15px rgba(247, 42, 48, 0.15);
        }

        .flow-node.firebolt-mcp-node {
          border-color: var(--accent-purple);
          box-shadow: 0 0 15px rgba(172, 36, 34, 0.15);
        }

        .node-icon {
          font-size: 32px;
          margin-bottom: 4px;
        }

        .node-label {
          font-weight: 600;
          font-size: 15px;
          color: var(--text-primary);
          line-height: 1.3;
        }

        .node-action {
          font-size: 12px;
          color: var(--accent-cyan);
          font-family: var(--font-mono);
          line-height: 1.4;
          word-break: break-word;
        }

        .flow-node.fml-node .node-action {
          color: var(--accent-fire);
        }

        .flow-node.ollama-node .node-action,
        .flow-node.embed-node .node-action {
          color: var(--accent-green);
        }

        .flow-node.firebolt-node .node-action {
          color: var(--accent-fire);
        }

        .flow-node.firebolt-mcp-node .node-action {
          color: var(--accent-purple);
        }

        .node-url {
          font-size: 10px;
          color: var(--text-muted);
          font-family: var(--font-mono);
          margin-top: 2px;
          word-break: break-all;
        }


        /* Step badges on nodes */
        .flow-step-badge {
          position: absolute;
          top: -14px;
          right: -14px;
          background: rgba(20, 20, 30, 0.95);
          border: 2px solid var(--accent-green);
          border-radius: 20px;
          padding: 5px 12px;
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          color: var(--text-primary);
          z-index: 20;
          white-space: nowrap;
        }

        .flow-step-badge.top {
          top: -14px;
          left: 50%;
          transform: translateX(-50%);
        }

        .flow-step-badge .step-num {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: var(--accent-green);
          color: #000;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 700;
          font-size: 12px;
        }

        .firebolt-node .flow-step-badge {
          border-color: var(--accent-fire);
        }

        .firebolt-node .flow-step-badge .step-num {
          background: var(--accent-fire);
        }


        /* Flow Legend */
        .flow-legend {
          display: flex;
          gap: 24px;
          margin-top: 16px;
          justify-content: center;
        }

        .legend-item {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
          color: var(--text-muted);
        }

        .legend-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
        }

        .legend-line {
          width: 30px;
          height: 3px;
          border-radius: 2px;
          display: inline-block;
        }

        .legend-line.request {
          background: var(--accent-cyan);
        }

        .legend-line.response {
          background: transparent;
          background-image: repeating-linear-gradient(
            90deg,
            var(--accent-green) 0px,
            var(--accent-green) 4px,
            transparent 4px,
            transparent 8px
          );
          border: 1px dashed var(--accent-green);
          height: 3px;
        }

        .legend-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
        }

        .legend-dot.local {
          background: var(--accent-green);
        }

        .legend-dot.cloud {
          background: var(--accent-purple);
        }

        .service-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }

        .service-name {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 14px;
          font-weight: 600;
          font-family: var(--font-mono);
          letter-spacing: 0.5px;
        }

        .service-icon {
          font-size: 16px;
        }

        .service-description {
          font-size: 12px;
          color: var(--text-muted);
          margin-bottom: 12px;
          line-height: 1.4;
        }

        .service-location {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 16px;
        }

        .location-badge {
          font-size: 10px;
          padding: 2px 8px;
          border-radius: 10px;
        }

        .location-badge.local {
          background: rgba(255, 72, 72, 0.15);
          color: var(--accent-green);
        }

        .location-badge.cloud {
          background: rgba(172, 36, 34, 0.15);
          color: var(--accent-purple);
        }

        .location-url {
          font-size: 10px;
          color: var(--text-muted);
          font-family: var(--font-mono);
        }

        .service-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }

        .service-status {
          font-size: 12px;
          color: var(--text-secondary);
        }

        .service-metrics {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 16px;
        }

        .metric {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .metric-label {
          font-size: 11px;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .metric-value {
          font-size: 16px;
          font-weight: 600;
          font-family: var(--font-mono);
        }

        .token-stats {
          display: flex;
          gap: 24px;
          padding-top: 12px;
          border-top: 1px solid var(--border-subtle);
          margin-bottom: 16px;
        }

        .token-stat {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .token-label {
          font-size: 11px;
          color: var(--text-muted);
        }

        .token-value {
          font-size: 14px;
          font-family: var(--font-mono);
          color: var(--accent-cyan);
        }

        .operation-chart {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid var(--border-subtle);
        }

        /* Charts Section */
        .charts-section {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
          margin-bottom: 32px;
        }

        .chart-card {
          background: var(--bg-card);
          border: 1px solid var(--border-subtle);
          border-radius: 16px;
          padding: 20px;
        }

        .chart-title {
          font-size: 14px;
          font-weight: 600;
          margin-bottom: 16px;
        }

        /* Calls Table */
        .calls-card {
          background: var(--bg-card);
          border: 1px solid var(--border-subtle);
          border-radius: 16px;
          padding: 20px;
        }

        .calls-table {
          font-family: var(--font-mono);
          font-size: 12px;
        }

        .calls-header {
          display: grid;
          grid-template-columns: 100px 1fr 80px 50px;
          gap: 12px;
          padding-bottom: 12px;
          border-bottom: 1px solid var(--border-subtle);
          color: var(--text-muted);
          text-transform: uppercase;
          font-size: 10px;
          letter-spacing: 0.5px;
        }

        .calls-row {
          display: grid;
          grid-template-columns: 100px 1fr 80px 50px;
          gap: 12px;
          padding: 10px 0;
          border-bottom: 1px solid var(--border-subtle);
        }

        .call-time {
          color: var(--text-muted);
        }

        .call-operation {
          color: var(--accent-cyan);
        }

        .call-latency {
          color: var(--text-secondary);
        }

        .call-status.success {
          color: var(--accent-green);
        }

        .call-status.error {
          color: var(--accent-fire);
        }

        /* Top Accessed */
        .top-accessed {
          background: var(--bg-card);
          border: 1px solid var(--border-subtle);
          border-radius: 16px;
          padding: 20px;
        }

        .memory-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .memory-item {
          display: flex;
          flex-direction: column;
          gap: 8px;
          padding: 14px 16px;
          background: var(--bg-secondary);
          border-radius: 8px;
        }

        .memory-header {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .memory-category {
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
          padding: 4px 8px;
          border-radius: 4px;
          text-align: center;
          color: var(--bg-primary);
        }

        .memory-content {
          font-size: 13px;
          line-height: 1.5;
          color: var(--text-primary);
          word-break: break-word;
        }

        .memory-access {
          font-size: 11px;
          color: var(--text-muted);
          margin-left: auto;
        }

        .memory-importance {
          width: 80px;
          height: 6px;
          background: var(--bg-card);
          border-radius: 3px;
          overflow: hidden;
        }

        .importance-bar {
          height: 100%;
          background: linear-gradient(90deg, var(--accent-fire), var(--accent-yellow));
          border-radius: 3px;
        }

        /* Responsive */
        @media (max-width: 1200px) {
          .stats-row {
            grid-template-columns: repeat(2, 1fr);
          }
          .services-grid {
            grid-template-columns: 1fr;
          }
          .charts-section {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 768px) {
          .stats-row {
            grid-template-columns: 1fr;
          }
          .dashboard-header {
            flex-direction: column;
            gap: 16px;
            align-items: flex-start;
          }
          .memory-header {
            flex-wrap: wrap;
          }
          .memory-importance {
            width: 60px;
          }
        }
      `}</style>
    </div>
  )
}
