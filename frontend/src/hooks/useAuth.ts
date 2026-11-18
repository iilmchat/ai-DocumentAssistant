import { useState, useEffect, useCallback } from 'react'
import { apiClient, tokenStore } from '../api/client'
import { UserInfo } from '../types'

export function useAuth() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) {
      setUser(null)
      setIsLoading(false)
      return
    }
    try {
      setUser(await apiClient.getCurrentUser())
    } catch {
      tokenStore.clear()
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
    tokenStore.clear()
    setUser(null)
  }, [])

  return { user, isLoading, refresh, logout }
}
