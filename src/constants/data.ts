import type { NewsCard } from '@/types'

export const SUGGESTIONS = [
  { label: 'Latest LLM benchmarks',          prompt: 'What are the latest LLM benchmarks?' },
  { label: 'Frontier model releases this week', prompt: 'Walk me through frontier model releases this week.' },
  { label: 'AI policy in the EU',             prompt: 'Catch me up on AI policy in the EU.' },
  { label: 'Open vs. closed models',          prompt: 'Where does the open-vs-closed model debate stand right now?' },
]

export const BENCHMARK_CARDS: NewsCard[] = [
  {
    id: 'c1', source: 'Artificial Analysis', time: '2h ago', kind: 'Benchmark', tone: 'lead', tag: 'Reasoning',
    title: 'GPT-5.1 edges Claude 4.5 on reasoning, trails on long-context recall',
    blurb: 'On the latest combined index, GPT-5.1 takes the lead on math and code, while Claude 4.5 holds long-context retrieval and tool-use. Gemini 3 closes the gap.',
  },
  {
    id: 'c2', source: 'LMSys Arena', time: '5h ago', kind: 'Leaderboard', tone: 'calm', tag: 'Open weights',
    title: 'Open-weights climb: Llama 4.1 enters Arena top five for the first time',
    blurb: 'Crowd-rated head-to-head puts Meta\'s Llama 4.1 within 18 Elo of the leading closed model. DeepSeek-R2 and Qwen 3 follow closely behind.',
  },
  {
    id: 'c3', source: 'MMLU-Pro', time: 'Yesterday', kind: 'Analysis', tone: 'calm', tag: 'Saturation',
    title: 'Saturation watch: top scores cluster within two points',
    blurb: 'Five frontier models now score within a narrow band on MMLU-Pro. Researchers argue the benchmark is approaching its ceiling and call for harder evals.',
  },
  {
    id: 'c4', source: 'SWE-bench Verified', time: 'Yesterday', kind: 'Coding', tone: 'calm', tag: 'Agents',
    title: 'Agentic coding scores jump 11 points after new tool-use protocol',
    blurb: 'After adopting a standardized tool-use schema, three frontier models posted double-digit gains on real-world software engineering tasks.',
  },
]

export const CARD_ACTIONS = [
  { id: 'report',  label: 'Make a report',   icon: 'doc' },
  { id: 'compare', label: 'Compare models',  icon: 'compare' },
  { id: 'explore', label: 'Explore deeper',  icon: 'compass' },
  { id: 'save',    label: 'Save thread',     icon: 'bookmark' },
]

export const FOLLOWUPS = [
  'Which benchmarks should I actually trust?',
  'How is GPT-5.1 different from Claude 4.5 in practice?',
  'Show me the open-weights leaderboard.',
  'Draft me a one-page summary I can share.',
]

export const TWEAKS_DEFAULTS = {
  palette: 'moss',
  displayFont: 'Instrument Serif',
  grain: 0.18,
  blur: 60,
  showSuggestions: true,
  compactMessages: false,
  tagline: 'Today in AI, gently unpacked.',
  newsFont: 'Bricolage Grotesque',
  preloadDemo: true,
}
