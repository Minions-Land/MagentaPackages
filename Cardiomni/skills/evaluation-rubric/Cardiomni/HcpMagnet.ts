import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Skill Source magnet for the Cardiomni package (source = "Cardiomni").
 *
 * Isomorphic to the host's skills/<skill>/<source>/HcpMagnet.ts (bare class,
 * static build, toResource). SKILL.md is resolved relative to this file so the
 * package stays relocatable.
 */
export class HcpMagnet {
	static readonly module = "skills/evaluation-rubric";
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
			name: "evaluation-rubric",
			source: "Cardiomni",
			mergeMode: "replace" as const,
			contentPath: join(dirname(fileURLToPath(import.meta.url)), "SKILL.md"),
		};
	}
}
