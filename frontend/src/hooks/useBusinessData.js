import { useCallback, useEffect, useState } from 'react';
import { SERVERS } from '../constants';
import { api } from '../services/api';

export function useBusinessData({ server, sort, capital, risk, strategy }) {
  const [strategies, setStrategies] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [names, setNames] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadStrategies = useCallback(async () => {
    try { setStrategies(await api.strategies()); } catch { setStrategies([]); }
  }, []);

  const loadNames = useCallback(async () => {
    setNames(await api.serverNames(SERVERS));
  }, []);

  const loadOpportunities = useCallback(async () => {
    setLoading(true);
    try {
      setOpportunities(await api.opportunities({ server, sort, capital, risk, strategy }));
      setError('');
    } catch (e) {
      setOpportunities([]);
      setError(e.message);
    } finally { setLoading(false); }
  }, [server, sort, capital, risk, strategy]);

  useEffect(() => { loadNames(); loadStrategies(); }, [loadNames, loadStrategies]);
  useEffect(() => { loadOpportunities(); }, [loadOpportunities]);

  const refresh = useCallback(async () => {
    await Promise.all([loadStrategies(), loadOpportunities()]);
  }, [loadStrategies, loadOpportunities]);

  return { strategies, opportunities, names, loading, error, refresh };
}

export function useMarketData({ itemId, city, quality, server }) {
  const [data, setData] = useState({ current: null, analysis: null, history: [], spread: null, error: '' });
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    if (!itemId || !city) return;
    setLoading(true);
    try { setData({ ...(await api.market({ itemId, city, quality, server })), error: '' }); }
    catch (e) { setData({ current: null, analysis: null, history: [], spread: null, error: e.message }); }
    finally { setLoading(false); }
  }, [itemId, city, quality, server]);
  return { ...data, loading, load };
}
