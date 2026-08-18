import { useCallback, useEffect, useState } from 'react'

/**
 * Load one API resource and track its lifecycle.
 *
 * `loader` runs whenever `deps` change. Pass `enabled: false` to hold off
 * until a dependency (a patient id, say) is actually available.
 */
export function useResource(loader, deps = [], { enabled = true, initial = null } = {}) {
  const [data, setData] = useState(initial)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(enabled)

  const run = useCallback(async () => {
    if (!enabled) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      setData(await loader())
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps])

  useEffect(() => { run() }, [run])

  return { data, error, loading, reload: run, setData }
}
