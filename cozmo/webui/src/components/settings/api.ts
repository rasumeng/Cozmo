import type { SettingsData } from './types'

const API_BASE = import.meta.env.DEV ? 'http://localhost:8765' : ''

export { API_BASE }

export async function fetchConfig(): Promise<SettingsData> {
  const r = await fetch(`${API_BASE}/api/config`)
  return r.json()
}

export async function saveConfig(patch: Record<string, unknown>) {
  await fetch(`${API_BASE}/api/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
}

export async function fetchOllamaModels(): Promise<string[]> {
  try {
    const r = await fetch(`${API_BASE}/api/ollama/models`)
    if (r.ok) return r.json()
  } catch {}
  return []
}

export async function fetchAvailableModels(): Promise<{ name: string; provider: string }[]> {
  try {
    const r = await fetch(`${API_BASE}/api/models/available`)
    if (r.ok) return r.json()
  } catch {}
  return []
}
