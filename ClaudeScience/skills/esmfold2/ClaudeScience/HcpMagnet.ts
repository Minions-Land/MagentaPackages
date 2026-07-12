import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Skill Source magnet for the ClaudeScience package (source = "ClaudeScience").
 *
 * Isomorphic to the host's skills/<skill>/<source>/HcpMagnet.ts (bare class,
 * static build, toResource). Per HCP spec §2 the magnet is a bare class whose
 * shape is validated structurally, so it imports no harness interface. SKILL.md
 * is resolved relative to this file so the package is relocatable when
 * downloaded into the local package cache.
 */
export class HcpMagnet {
	static readonly module = "skills/esmfold2";
	static readonly kind = "skill";
	static readonly source = "ClaudeScience";
	static build(_context: unknown) {
		return new HcpMagnet();
	}

	readonly kind = "resource:skill";
	readonly source = "ClaudeScience";

	toResource() {
		return {
			kind: "skill",
			name: "esmfold2",
			source: "ClaudeScience",
			mergeMode: "replace" as const,
			contentPath: join(dirname(fileURLToPath(import.meta.url)), "SKILL.md"),
		};
	}
}
