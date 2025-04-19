/**
 * Welcome to Cloudflare Workers! This is your first worker.
 *
 * - Run `npm run dev` in your terminal to start a development server
 * - Open a browser tab at http://localhost:8787/ to see your worker in action
 * - Run `npm run deploy` to publish your worker
 *
 * Bind resources to your worker in `wrangler.jsonc`. After adding bindings, a type definition for the
 * `Env` object can be regenerated with `npm run cf-typegen`.
 *
 * Learn more at https://developers.cloudflare.com/workers/
 */

export default {
	async fetch(request, env, ctx): Promise<Response> {
	  const url = new URL(request.url);
	  
	  // Обработка CORS preflight
	  if (request.method === "OPTIONS") {
		return new Response(null, {
		  status: 204,
		  headers: {
			'Access-Control-Allow-Origin': '*',
			'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
			'Access-Control-Allow-Headers': 'Content-Type, Authorization',
			'Access-Control-Max-Age': '86400',
		  },
		});
	  }
	  
	  // Проксирование API запросов
	  if (url.pathname.startsWith('/api/')) {
		const backendUrl = new URL(url.pathname.replace(/^\/api/, ''), 
								  env.BACKEND_URL || 'https://aiassistantontelegrambot.uk');
		
		const backendRequest = new Request(backendUrl.toString(), {
		  method: request.method,
		  headers: request.headers,
		  body: request.body,
		  redirect: 'follow',
		});
		
		try {
		  const response = await fetch(backendRequest);
		  const newHeaders = new Headers(response.headers);
		  newHeaders.set('Access-Control-Allow-Origin', '*');
		  
		  return new Response(response.body, {
			status: response.status,
			headers: newHeaders,
		  });
		} catch (error) {
		  return new Response(JSON.stringify({error: error.message}), { 
			status: 500,
			headers: {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
		  });
		}
	  }
	  
	  // Существующие эндпоинты
	  switch (url.pathname) {
		case '/message': return new Response('Hello, World!');
		case '/random': return new Response(crypto.randomUUID());
		default: return env.ASSETS.fetch(request);
	  }
	},
  } satisfies ExportedHandler<Env>;