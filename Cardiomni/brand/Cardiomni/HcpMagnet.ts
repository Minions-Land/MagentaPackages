import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Brand Source magnet for the Cardiomni package (source = "Cardiomni").
 *
 * Isomorphic to the host's brand/<source>/HcpMagnet.ts. Bare class, static
 * build, toResource (HCP spec §2 — no imported interface). The brand descriptor
 * (brand.toml) is resolved relative to this magnet file so the package stays
 * relocatable when downloaded into the local package cache.
 */
export class HcpMagnet {
	static readonly module = "brand";
	static readonly kind = "brand";
	static readonly source = "Cardiomni";
	static build(_context: unknown) {
		return new HcpMagnet();
	}

	readonly kind = "resource:brand";
	readonly source = "Cardiomni";

	toResource() {
		return {
			kind: "brand",
			name: "Cardiomni",
			source: "Cardiomni",
			mergeMode: "replace" as const,
			contentPath: join(dirname(fileURLToPath(import.meta.url)), "brand.toml"),
		};
	}
}
