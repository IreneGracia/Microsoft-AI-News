import type { User } from '@/types'

export function readSession(): User | null {
  try {
    const raw = localStorage.getItem('mai_user')
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export function writeSession(user: User | null): void {
  try {
    if (user) localStorage.setItem('mai_user', JSON.stringify(user))
    else localStorage.removeItem('mai_user')
  } catch {
    // ignore
  }
}
