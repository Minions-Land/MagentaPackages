import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Tool Source magnet for the AutOmicScience package (source = "AutOmicScience").
 * Isomorphic to host tools/<tool>/<source>/HcpMagnet.ts: one tool item, one
 * descriptor, resolved relative to this file for relocatable loading.
 */
export class HcpMagnet {
	static readonly module = "tools/omics-install";
	static readonly kind = "tool";
	static readonly source = "AutOmicScience";
	static build(context: unknown) {
		return new HcpMagnet(context);
	}

	readonly kind = "tool";
	readonly source = "AutOmicScience";
	readonly descriptorPath = join(dirname(fileURLToPath(import.meta.url)), "omics-install.toml");
	private readonly context: unknown;

	constructor(context: unknown) {
		this.context = context;
	}

	descriptor() {
		return { kind: "tool" as const, name: "omics-install", source: "AutOmicScience", descriptorPath: this.descriptorPath };
	}
}
