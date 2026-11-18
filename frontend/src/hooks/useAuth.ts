import { useState, useEffect, useCallback } from 'react'
import { apiClient, refreshTokens, tokenStore } from '../api/client'
import { UserInfo } from '../types'

export function useAuth() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refresh = useCallback(async () => {
    // access-токен мог истечь — пробуем refresh перед тем, как считать сессию потерянной
    if (!tokenStore.get() && tokenStore.getRefresh()) {
      await refreshTokens()
    }
    if (!tokenStore.get()) {
      setUser(null)
      setIsLoading(false)
      return
    }
    try {
      setUser(await apiClient.getCurrentUser())
    } catch {
      tokenStore.clearAll()
      setUser(null)
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
