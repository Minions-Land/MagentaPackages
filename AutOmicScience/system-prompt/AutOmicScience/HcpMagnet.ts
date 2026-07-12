import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * System-prompt Source magnet for the AutOmicScience package (source = "AutOmicScience").
 *
 * Isomorphic to the host's system-prompt/<source>/HcpMagnet.ts. This package
 * contributes an append-mode system prompt, so mergeMode is "append" and the
 * descriptor (system-prompt.toml) is resolved relative to this magnet file.
 */
export class HcpMagnet {
	static readonly module = "system-prompt";
	static readonly kind = "system-prompt";
	static readonly source = "AutOmicScience";
	static build(_context: unknown) {
		return new HcpMagnet();
	}

	readonly kind = "resource:system-prompt";
	readonly source = "AutOmicScience";

	toResource() {
		return {
			kind: "system-prompt",
			name: "system-prompt",
			source: "AutOmicScience",
			mergeMode: "append" as const,
			descriptorPath: join(dirname(fileURLToPath(import.meta.url)), "system-prompt.toml"),
		};
	}
}
