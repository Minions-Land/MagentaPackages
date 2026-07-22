import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Skill Source magnet for the Cardiomni package (source = "Cardiomni").
 *
 * Isomorphic to the host's skills/<skill>/<source>/HcpMagnet.ts (bare class,
 * static build, toResource). Per HCP spec §2 the magnet is a bare class whose
 * shape is validated structurally, so it imports no harness interface. SKILL.md
 * is resolved relative to this file so the package stays relocatable.
 */
export class HcpMagnet {
	static readonly module = "skills/diagnosis-analysis";
	static readonly kind = "skill";
	static readonly source = "Cardiomni";
	static build(_context: unknown) {
		return new HcpMagnet();
	}

	readonly kind = "resource:skill";
	readonly source = "Cardiomni";

	toResource() {
		return {
			kind: "skill",
			name: "diagnosis-analysis",
			source: "Cardiomni",
			mergeMode: "replace" as const,
			contentPath: join(dirname(fileURLToPath(import.meta.url)), "SKILL.md"),
		};
	}
}
