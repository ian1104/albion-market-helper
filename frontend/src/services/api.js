const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export const api = {
  async strategies() {
    const data = await request('/api/strategies');
    return data.strategies || [];
  },
  async opportunities({ server, sort, capital, risk, strategy, limit = 12 }) {
    const q = new URLSearchParams({ server, sort, limit: String(limit) });
    if (capital !== '') q.set('capital', capital);
    if (risk) q.set('risk', risk);
    if (strategy) q.set('strategy', strategy);
    const data = await request(`/api/opportunities?${q}`);
    return data.opportunities || [];
  },
  async serverNames(servers) {
    const entries = await Promise.all(servers.map(async id => {
      try {
        const data = await request(`/api/sources?server=${id}`);
        return [id, data.server_name || id];
      } catch {
        return [id, id];
      }
    }));
    return Object.fromEntries(entries);
  },
  async market({ itemId, city, quality, server }) {
    const q = new URLSearchParams({ item_id: itemId, city, quality, server });
    const spreadQuery = new URLSearchParams({ item_id: itemId, quality, server, range: '24h' });
    const [currentResponse, analysisResponse, historyResponse, spreadResponse] = await Promise.all([
      fetch(`${API}/api/market/prices?${q}`),
      fetch(`${API}/api/market/analysis?${q}&range=24h`),
      fetch(`${API}/api/market/history?${q}`),
      fetch(`${API}/api/market/spread?${spreadQuery}`),
    ]);
    if (!currentResponse.ok || !analysisResponse.ok || !historyResponse.ok) {
      throw new Error('시장 API 요청에 실패했습니다.');
    }
    return {
      current: (await currentResponse.json())[0],
      analysis: await analysisResponse.json(),
      history: await historyResponse.json(),
      spread: spreadResponse.ok ? await spreadResponse.json() : null,
    };
  },
};

export { API };
