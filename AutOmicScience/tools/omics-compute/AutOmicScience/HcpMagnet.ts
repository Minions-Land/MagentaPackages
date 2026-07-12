import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Tool Source magnet for the AutOmicScience package (source = "AutOmicScience").
 *
 * Isomorphic to the host's tools/<tool>/<source>/HcpMagnet.ts. Bare class,
 * static build, descriptor (HCP spec §2 — no imported interface). This is a
 * descriptor-backed tool: the magnet resolves its own tool descriptor
 * (omics-compute.toml) relative to this file and hands it to the host tool runtime at
 * assembly time. The package ships standalone, so the descriptor path is
 * relocatable with the package.
 */
export class HcpMagnet {
	static readonly module = "tools/omics-compute";
	static readonly kind = "tool";
	static readonly source = "AutOmicScience";
	static build(context: unknown) {
		return new HcpMagnet(context);
	}

	readonly kind = "tool";
	readonly source = "AutOmicScience";
	readonly descriptorPath = join(dirname(fileURLToPath(import.meta.url)), "omics-compute.toml");
	private readonly context: unknown;

	constructor(context: unknown) {
		this.context = context;
	}

	descriptor() {
		return {
			kind: "tool" as const,
			name: "omics-compute",
			source: "AutOmicScience",
			descriptorPath: this.descriptorPath,
		};
	}
}
