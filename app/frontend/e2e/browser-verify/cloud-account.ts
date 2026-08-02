/**
 * Read a real cloud account, for the export round trip (`A1`).
 *
 * WHY THIS EXISTS. `POST /export/cloud` answering 200 proves the request was accepted — not that a
 * valid PNG landed in the user's Drive. Both of Track E's predicted failure modes would have
 * returned a plausible 200 while writing nothing usable, and one of them (a followed 308 on Drive's
 * session init) really did upload the 17-byte *metadata* in a redirect loop instead of the figure.
 * So the check is: list before, export through the UI, find what is new, **download it and look at
 * the bytes**, then delete it again.
 *
 * DELETING IS PART OF THE CHECK, not tidiness. These are the owner's real accounts, and this spec
 * re-runs on every browser-verify sweep; a check that litters someone's Drive gets switched off.
 *
 * Both providers are sandboxed to what Selom created (Drive `drive.file`, Dropbox App Folder —
 * `docs/cloud-providers-contract/spec.md` §Scope), which is what makes "list the account" a safe and
 * meaningful operation here: it can only ever see this app's own files.
 */
import { nangoConfig } from "../../scripts/browser-verify/paths.mjs";

export type CloudFile = { id: string; name: string; size: number };

/** Mint an access token for the same connection the app itself used. */
async function accessToken(providerConfigKey: string, connectionId: string): Promise<string> {
  const { baseUrl, secretKey } = nangoConfig();
  const url = `${baseUrl}/connection/${connectionId}?provider_config_key=${providerConfigKey}`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${secretKey}` } });
  if (!r.ok) throw new Error(`Nango refused a token for ${providerConfigKey} (HTTP ${r.status})`);
  const body = (await r.json()) as { credentials?: { access_token?: string } };
  const token = body.credentials?.access_token;
  if (!token) throw new Error(`no access token in the Nango response for ${providerConfigKey}`);
  return token;
}

/** A PNG's magic number and its IHDR dimensions — "is this actually an image?", from the bytes. */
export function pngInfo(bytes: Uint8Array): { valid: boolean; width: number; height: number } {
  const magic = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  const valid = magic.every((b, i) => bytes[i] === b);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return valid
    ? { valid, width: view.getUint32(16), height: view.getUint32(20) }
    : { valid, width: 0, height: 0 };
}

export interface CloudAccount {
  /** Every file this app can see — for Drive that is only what it created (`drive.file`). */
  list(): Promise<CloudFile[]>;
  download(id: string): Promise<Uint8Array>;
  remove(id: string): Promise<void>;
}

function googleAccount(connectionId: string): CloudAccount {
  const auth = async () => ({ Authorization: `Bearer ${await accessToken("google-drive", connectionId)}` });
  return {
    async list() {
      const url =
        "https://www.googleapis.com/drive/v3/files?q=trashed%20%3D%20false" +
        "&fields=files(id,name,size)&pageSize=200";
      const r = await fetch(url, { headers: await auth() });
      if (!r.ok) throw new Error(`Drive list failed (HTTP ${r.status})`);
      const body = (await r.json()) as { files?: { id: string; name: string; size?: string }[] };
      return (body.files ?? []).map((f) => ({ id: f.id, name: f.name, size: Number(f.size ?? 0) }));
    },
    async download(id) {
      const r = await fetch(`https://www.googleapis.com/drive/v3/files/${id}?alt=media`, {
        headers: await auth(),
      });
      if (!r.ok) throw new Error(`Drive download failed (HTTP ${r.status})`);
      return new Uint8Array(await r.arrayBuffer());
    },
    async remove(id) {
      const r = await fetch(`https://www.googleapis.com/drive/v3/files/${id}`, {
        method: "DELETE",
        headers: await auth(),
      });
      if (!r.ok && r.status !== 404) throw new Error(`Drive delete failed (HTTP ${r.status})`);
    },
  };
}

function dropboxAccount(connectionId: string): CloudAccount {
  const auth = async () => ({ Authorization: `Bearer ${await accessToken("dropbox", connectionId)}` });
  return {
    async list() {
      const r = await fetch("https://api.dropboxapi.com/2/files/list_folder", {
        method: "POST",
        headers: { ...(await auth()), "Content-Type": "application/json" },
        body: JSON.stringify({ path: "", recursive: true }),
      });
      if (!r.ok) throw new Error(`Dropbox list failed (HTTP ${r.status})`);
      const body = (await r.json()) as {
        entries?: { ".tag": string; id: string; name: string; size?: number }[];
      };
      return (body.entries ?? [])
        .filter((e) => e[".tag"] === "file")
        .map((e) => ({ id: e.id, name: e.name, size: e.size ?? 0 }));
    },
    async download(id) {
      const r = await fetch("https://content.dropboxapi.com/2/files/download", {
        method: "POST",
        // ASCII-only by construction — the same constraint the connector is held to.
        headers: { ...(await auth()), "Dropbox-API-Arg": JSON.stringify({ path: id }) },
      });
      if (!r.ok) throw new Error(`Dropbox download failed (HTTP ${r.status})`);
      return new Uint8Array(await r.arrayBuffer());
    },
    async remove(id) {
      const r = await fetch("https://api.dropboxapi.com/2/files/delete_v2", {
        method: "POST",
        headers: { ...(await auth()), "Content-Type": "application/json" },
        body: JSON.stringify({ path: id }),
      });
      if (!r.ok) throw new Error(`Dropbox delete failed (HTTP ${r.status})`);
    },
  };
}

export function cloudAccount(provider: string, connectionId: string): CloudAccount {
  if (provider === "google") return googleAccount(connectionId);
  if (provider === "dropbox") return dropboxAccount(connectionId);
  throw new Error(`no account reader for provider '${provider}'`);
}

/** Is the broker configured at all? Unset credentials must SKIP loudly, never pass quietly. */
export function brokerConfigured(): boolean {
  const { baseUrl, secretKey } = nangoConfig();
  return Boolean(baseUrl && secretKey);
}
