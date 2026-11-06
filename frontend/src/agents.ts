import type { AgentName } from './api'

export interface AgentMeta {
  name: AgentName
  label: string
  role: string
  initials: string
  color: string // accent for avatar, lane and chips
}

export const AGENTS: AgentMeta[] = [
  { name: 'boss', label: 'Boss', role: 'Routes tickets · final call', initials: 'BO', color: '#00356b' },
  { name: 'inventory', label: 'Inventory', role: 'Stock · vendors · restock', initials: 'IN', color: '#0f7c7a' },
  { name: 'accounting', label: 'Accounting', role: 'Cash · invoices · margins', initials: 'AC', color: '#a46b00' },
  { name: 'facilities', label: 'Facilities', role: 'Lease · rent · space', initials: 'FA', color: '#b5492f' },
  { name: 'customer_service', label: 'Customer Service', role: 'Drafts replies', initials: 'CS', color: '#6b4fa3' },
]

export const AGENT: Record<AgentName, AgentMeta> = Object.fromEntries(AGENTS.map((a) => [a.name, a])) as Record<
  AgentName,
  AgentMeta
>

export const TICKET_TYPE: Record<string, { label: string; icon: string }> = {
  customer_order: { label: 'Customer order', icon: '🛍️' },
  rent_notice: { label: 'Rent notice', icon: '🏠' },
  price_override: { label: 'Discount request', icon: '🏷️' },
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
