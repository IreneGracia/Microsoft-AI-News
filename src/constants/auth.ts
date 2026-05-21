import type { MockAccount } from '@/types'

export const CORPORATE_DOMAIN = 'microsoft.com'

export const DEPARTMENTS = [
  'Engineering', 'Cloud + AI', 'Azure', 'Research', 'Product',
  'Security', 'Marketing', 'Sales', 'Customer Success',
  'Consulting Services', 'Legal & Compliance', 'Finance',
  'Operations', 'HR / People', 'Other',
]

export const REGIONS_AUTH = [
  { id: 'na',    label: 'North America' },
  { id: 'eu',    label: 'Europe' },
  { id: 'china', label: 'Greater China' },
  { id: 'apac',  label: 'Asia Pacific' },
  { id: 'india', label: 'India' },
  { id: 'latam', label: 'Latin America' },
  { id: 'mea',   label: 'Middle East & Africa' },
]

export const MOCK_MS_ACCOUNTS: MockAccount[] = [
  { name: 'Eve Sandoval', email: 'eve.sandoval@microsoft.com', department: 'Cloud + AI', region: 'eu',    initial: 'e', color: '#0078D4' },
  { name: 'Daniel Kim',   email: 'daniel.kim@microsoft.com',   department: 'Azure',      region: 'na',    initial: 'd', color: '#7FBA00' },
  { name: 'Priya Iyer',   email: 'priya.iyer@microsoft.com',   department: 'Research',   region: 'india', initial: 'p', color: '#F25022' },
]
