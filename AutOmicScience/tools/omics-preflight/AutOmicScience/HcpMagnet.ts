import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Tool Source magnet for the AutOmicScience package (source = "AutOmicScience").
 *
 * Isomorphic to the host's tools/<tool>/<source>/HcpMagnet.ts. The package
 * Source keeps its HcpMagnet identity while the Client-owned builder creates
 * the host-backed Tool product from the relocatable descriptor.
 */
export class HcpMagnet {
	static readonly module = "tools/omics-preflight";
	static readonly kind = "tool";
	static readonly source = "AutOmicScience";
	static async build(context: HcpMagnetBuildContext) {
		const products = await HcpMagnetbuildtools(context, {
			kind: "tool",
			name: "omics-preflight",
			source: "AutOmicScience",
			descriptorPath: join(dirname(fileURLToPath(import.meta.url)), "omics-preflight.toml"),
		});
		return products.map((product) => new HcpMagnet(product));
	}

	readonly kind: string;
	readonly source = "AutOmicScience";
	private readonly product: HcpMagnettoolproduct;

	constructor(product: HcpMagnettoolproduct) {
		this.product = product;
		this.kind = product.kind;
	}

	toTool() {
		return this.product.toTool();
	}

	async dispose() {
		await this.product.close?.();
	}
}

type HcpMagnetBuildContext = {
	repoRoot: string;
	resolveCapability?<T>(name: string): T | undefined;
	cwd?: string;
	kind: string;
	name: string;
	descriptorPath?: string;
	source: string;
	settings?: {
		HcpClientbuildtools?: (
			descriptor: HcpClientpackagetooldescriptor,
			context: HcpMagnetBuildContext,
		) => Promise<HcpMagnettoolproduct[]>;
	};
	description?: string;
	hotSwappable?: boolean;
};

type HcpClientpackagetooldescriptor = {
	kind: "tool";
	name: string;
	source: string;
	descriptorPath: string;
};

type HcpMagnettoolproduct = {
	readonly kind: string;
	toTool(): unknown;
	close?(): void | Promise<void>;
};

async function HcpMagnetbuildtools(
	context: HcpMagnetBuildContext,
	descriptor: HcpClientpackagetooldescriptor,
): Promise<HcpMagnettoolproduct[]> {
	const build = context.settings?.HcpClientbuildtools;
	if (typeof build !== "function") {
		throw new Error(`Package tool ${descriptor.name} has no HcpClient Tool builder.`);
	}
	return build(descriptor, context);
}
