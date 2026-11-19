import { useState, useEffect, useCallback } from 'react'
import { apiClient, refreshTokens } from '../api/client'
import { UserInfo } from '../types'

export function useAuth() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refresh = useCallback(async () => {
    // T8: сессия живёт в httpOnly cookie. Если access истёк, /me вернёт 401 и
    // authFetch сам попробует refresh (см. client.ts).
    try {
      setUser(await apiClient.getCurrentUser())
    } catch {
      await refreshTokens()
      try {
        setUser(await apiClient.getCurrentUser())
      } catch {
        setUser(null)
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const onLogout = () => setUser(null)
    window.addEventListener('auth:logout', onLogout)
    return () => window.removeEventListener('auth:logout', onLogout)
  }, [refresh])

  const logout = useCallback(() => {
    void apiClient.logout()
    setUser(null)
  }, [])

  return { user, isLoading, refresh, logout }
}
