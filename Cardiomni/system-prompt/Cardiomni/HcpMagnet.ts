import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * System-prompt Source magnet for the Cardiomni package (source = "Cardiomni").
 *
 * Isomorphic to the host's system-prompt/<source>/HcpMagnet.ts. This package
 * contributes an append-mode system prompt, so mergeMode is "append" and the
 * content (SYSTEM.md) is resolved relative to this magnet file.
 */
export class HcpMagnet {
	static readonly module = "system-prompt";
	static readonly kind = "system-prompt";
	static readonly source = "Cardiomni";
	static build(_context: unknown) {
		return new HcpMagnet();
	}

	readonly kind = "resource:system-prompt";
	readonly source = "Cardiomni";

	toResource() {
		return {
			kind: "system-prompt",
			name: "system-prompt",
			source: "Cardiomni",
			mergeMode: "append" as const,
			contentPath: join(dirname(fileURLToPath(import.meta.url)), "SYSTEM.md"),
		};
	}
}
