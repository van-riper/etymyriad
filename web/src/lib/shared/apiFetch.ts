import { browser } from '$app/environment';
import { toast } from 'svelte-sonner';

const WARMUP_DELAY_MS = 1200;

type ErrorBody = { message?: string };

export async function apiFetch(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<Response> {
  let loadingToastId: string | number | undefined;
  const warmupTimer = browser
    ? setTimeout(() => {
        loadingToastId = toast.loading('The cluster is starting, please wait');
      }, WARMUP_DELAY_MS)
    : undefined;

  let res: Response;
  try {
    res = await fetchFn(url);
  } finally {
    clearTimeout(warmupTimer);
  }

  if (browser) {
    if (loadingToastId !== undefined) toast.dismiss(loadingToastId);
    if (!res.ok) await reportError(res);
  }
  return res;
}

async function reportError(res: Response): Promise<void> {
  if (res.status === 429) {
    toast.warning("You've sent too many requests");
    return;
  }
  const body = (await res
    .clone()
    .json()
    .catch(() => null)) as ErrorBody | null;
  const message = body?.message ?? `Request failed (${res.status})`;
  toast.error(message);
}
