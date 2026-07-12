import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Skill Source magnet for the AutOmicScience package (source = "AutOmicScience").
 *
 * Isomorphic to the host's skills/<skill>/<source>/HcpMagnet.ts (bare class,
 * static build, toResource). Per HCP spec §2 the magnet is a bare class whose
 * shape is validated structurally, so it imports no harness interface. The
 * package ships standalone, so SKILL.md is resolved relative to this file
 * rather than the harness skills dir, and the returned resource is the plain
 * HcpMagnetResource shape the assembly layer consumes.
 */
export class HcpMagnet {
	static readonly module = "skills/cancer-dependency";
	static readonly kind = "skill";
	static readonly source = "AutOmicScience";
	static build(_context: unknown) {
		return new HcpMagnet();
	}

	readonly kind = "resource:skill";
	readonly source = "AutOmicScience";

	toResource() {
		return {
			kind: "skill",
			name: "cancer-dependency",
			source: "AutOmicScience",
			mergeMode: "replace" as const,
			contentPath: join(dirname(fileURLToPath(import.meta.url)), "SKILL.md"),
		};
	}
}
