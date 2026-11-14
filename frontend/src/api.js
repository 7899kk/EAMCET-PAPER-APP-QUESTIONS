// Use the origin rather than the document URL: browsers reject fetch URLs
// containing HTTP-login credentials, even when resolving a relative path.
export function apiUrl(path, origin = window.location.origin) {
  const base = new URL(origin);
  const url = new URL(path, base.origin);
  if (url.origin !== base.origin) throw new Error('The PDF API must use this site’s origin.');
  return url.href;
}

export async function fetchServer(path, options = {}) {
  let response;
  try {
    response = await fetch(apiUrl(path), { ...options, credentials: 'same-origin' });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Could not reach the PDF server. Check your connection, then reload and sign in again. If the free server is waking up, wait about a minute and retry.');
  }
  if (response.status === 401) {
    throw new Error('Your editor sign-in expired. Reload this page and sign in again.');
  }
  return response;
}

export async function stableUpload(file) {
  if (file.size > 25 * 1024 * 1024) throw new Error('Choose a file smaller than 25 MB.');
  try {
    const bytes = await file.arrayBuffer();
    return new File([bytes], file.name, { type: file.type || 'application/octet-stream' });
  } catch {
    throw new Error('The selected file could not be read. Save a copy to this device and select that copy again.');
  }
}
