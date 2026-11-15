export class HoundSearch {
  constructor({ endpoint = 'http://127.0.0.1:8082', apiKey, fetchImpl = globalThis.fetch }) {
    const u = new URL(endpoint);
    if (u.username || u.password || u.search || u.hash || (u.protocol !== 'https:' && !(u.protocol === 'http:' && ['localhost','127.0.0.1','[::1]'].includes(u.hostname)))) throw new Error('Use HTTPS or loopback HTTP');
    this.endpoint = endpoint.replace(/\/$/, ''); this.apiKey = apiKey; this.fetch = fetchImpl;
  }
  async request(path, body, method = 'POST') {
    const response = await this.fetch(this.endpoint + path, {method, redirect:'error', headers:{Authorization:`Bearer ${this.apiKey}`, 'Content-Type':'application/json', ...(method==='POST'?{'Idempotency-Key':crypto.randomUUID()}: {})}, ...(body?{body:JSON.stringify(body)}:{})});
    if (!response.ok) throw new Error(`HoundSearch HTTP ${response.status}`);
    return response.status===204 ? null : response.json();
  }
  search(query, options={}) { return this.request('/v1/search',{query,...options}); }
  contents(urls, options={}) { return this.request('/v1/contents',{urls,...options}); }
  similar(url, options={}) { return this.request('/v1/find-similar',{url,...options}); }
  answer(query, model_profile, options={}) { return this.request('/v1/answer',{query,model_profile,...options}); }
  research(query, model_profile, options={}) { return this.request('/v1/research',{query,model_profile,...options}); }
  job(id) { return this.request('/v1/jobs/'+encodeURIComponent(id),null,'GET'); }
}
