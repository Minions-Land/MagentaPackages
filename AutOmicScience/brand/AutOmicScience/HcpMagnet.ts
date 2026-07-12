import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Brand Source magnet for the AutOmicScience package (source = "AutOmicScience").
 *
 * Isomorphic to the host's brand/<source>/HcpMagnet.ts. Bare class, static
 * build, toResource (HCP spec §2 — no imported interface). The brand descriptor
 * (brand.toml) is resolved relative to this magnet file so the package stays
 * relocatable when downloaded into the local package cache.
 */
export class HcpMagnet {
	static readonly module = "brand";
	static readonly kind = "brand";
	static readonly source = "AutOmicScience";
	static build(_context: unknown) {
		return new HcpMagnet();
	}

	readonly kind = "resource:brand";
	readonly source = "AutOmicScience";

	toResource() {
		return {
			kind: "brand",
			name: "AutOmicScience",
			source: "AutOmicScience",
			mergeMode: "replace" as const,
			descriptorPath: join(dirname(fileURLToPath(import.meta.url)), "brand.toml"),
		};
	}
}
