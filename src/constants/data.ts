import type { NewsCard } from '@/types'

export const SUGGESTIONS = [
  { label: 'Latest LLM benchmarks',          prompt: 'What are the latest LLM benchmarks?' },
  { label: 'Frontier model releases this week', prompt: 'Walk me through frontier model releases this week.' },
  { label: 'AI policy in the EU',             prompt: 'Catch me up on AI policy in the EU.' },
  { label: 'Open vs. closed models',          prompt: 'Where does the open-vs-closed model debate stand right now?' },
]

export const TOPIC_SUGGESTIONS: Record<string, { label: string; prompt: string }> = {
  ai_ml:     { label: 'Latest AI & ML news',              prompt: 'What are the latest AI and ML developments this week?' },
  cyber:     { label: 'Cybersecurity threats',            prompt: 'What are the biggest cybersecurity stories right now?' },
  cloud:     { label: 'Cloud & infrastructure updates',   prompt: 'What\'s new in cloud and infrastructure this week?' },
  softdev:   { label: 'Software development trends',      prompt: 'What are the most important software development trends right now?' },
  hardware:  { label: 'Chips & hardware news',            prompt: 'What\'s happening in chips and hardware this week?' },
  privacy:   { label: 'Data & privacy updates',           prompt: 'What are the latest data privacy developments?' },
  quantum:   { label: 'Quantum computing progress',       prompt: 'What\'s new in quantum computing?' },
  robotics:  { label: 'Robotics & automation news',       prompt: 'What are the latest robotics and automation stories?' },
  fintech:   { label: 'Fintech & payments news',          prompt: 'What\'s happening in fintech and payments this week?' },
  health:    { label: 'Health & biotech updates',         prompt: 'What are the biggest health tech and biotech stories?' },
  cleantech: { label: 'Clean tech & sustainability',      prompt: 'What\'s new in clean tech and sustainability?' },
  space:     { label: 'Space & satellite updates',        prompt: 'What\'s the latest in space and satellite technology?' },
  xr:        { label: 'Metaverse & XR news',              prompt: 'What\'s new in metaverse and XR this week?' },
  ma:        { label: 'M&A & funding rounds',             prompt: 'What are the biggest M&A deals and funding rounds this week?' },
  ipo:       { label: 'IPO & market news',                prompt: 'What\'s happening in tech IPOs and markets?' },
  bigtech:   { label: 'Big Tech news',                    prompt: 'What are the biggest stories from FAANG and Microsoft this week?' },
  startups:  { label: 'Startups & venture capital',       prompt: 'What are the most interesting startup and VC stories right now?' },
  layoffs:   { label: 'Layoffs & hiring trends',          prompt: 'What\'s happening with tech layoffs and hiring?' },
  earnings:  { label: 'Earnings & revenue updates',       prompt: 'What are the latest tech earnings and revenue results?' },
  ai_reg:    { label: 'AI regulation news',               prompt: 'What\'s new in AI regulation and policy?' },
  gdpr:      { label: 'Data protection updates',          prompt: 'What are the latest GDPR and data protection developments?' },
  antitrust: { label: 'Antitrust & competition',          prompt: 'What\'s happening in tech antitrust and competition cases?' },
  exports:   { label: 'Export controls & sanctions',      prompt: 'What are the latest export controls affecting tech?' },
  digiinfra: { label: 'Digital infrastructure policy',   prompt: 'What\'s new in digital infrastructure policy?' },
  cyberpol:  { label: 'Cybersecurity policy',            prompt: 'What\'s happening in cybersecurity policy and regulation?' },
  platform:  { label: 'Platform regulation news',        prompt: 'What are the latest platform regulation developments?' },
}

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
