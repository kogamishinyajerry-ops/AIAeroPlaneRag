/**
 * Unit tests for inferAgency function (JavaScript)
 * Run: node tests/unit/test_infer_agency.js
 *
 * Tests: group field priority, CCAR/FAR/CS prefix detection, edge cases
 */

// Copy of the inferAgency function from ui/app.js
function inferAgency(node) {
    // First check explicit group field
    const group = node.group || "";
    if (group === "CAAC" || group === "FAA" || group === "EASA") {
        return group;
    }
    // Infer from document field (e.g., "CCAR-33-R2", "FAR-33", "CS-E")
    // Strip known agency prefixes first (e.g., "caac-ccar-33-r2" → "CCAR-33-R2")
    const raw = (node.document || node.id || "").toUpperCase();
    const doc = raw
        .replace(/^CAAC-/, "")
        .replace(/^FAA-/, "")
        .replace(/^EASA-/, "");
    if (doc.startsWith("CCAR-") || doc.startsWith("AP-") || doc.startsWith("AC-")) {
        return "CAAC";
    }
    if (doc.startsWith("FAR-")) {
        return "FAA";
    }
    if (doc.startsWith("CS-")) {
        return "EASA";
    }
    return "";
}

// Test utilities
let passed = 0;
let failed = 0;

function assertEqual(actual, expected, testName) {
    if (actual === expected) {
        console.log(`  ✓ ${testName}`);
        passed++;
    } else {
        console.log(`  ✗ ${testName}`);
        console.log(`    Expected: "${expected}", Got: "${actual}"`);
        failed++;
    }
}

function assertTrue(condition, testName) {
    if (condition) {
        console.log(`  ✓ ${testName}`);
        passed++;
    } else {
        console.log(`  ✗ ${testName}`);
        console.log(`    Expected truthy, got: ${condition}`);
        failed++;
    }
}

console.log("=== inferAgency Unit Tests ===\n");

// Group field priority tests
console.log("Group field priority:");
assertEqual(inferAgency({group: "CAAC"}), "CAAC", "group=CAAC returns CAAC");
assertEqual(inferAgency({group: "FAA"}), "FAA", "group=FAA returns FAA");
assertEqual(inferAgency({group: "EASA"}), "EASA", "group=EASA returns EASA");

// Group overrides document
assertEqual(inferAgency({group: "FAA", document: "CCAR-33-R2"}), "FAA", "group=FAA overrides document=CCAR-33-R2");
assertEqual(inferAgency({group: "CAAC", document: "FAR-25"}), "CAAC", "group=CAAC overrides document=FAR-25");
assertEqual(inferAgency({group: "EASA", document: "CS-E"}), "EASA", "group=EASA overrides document=CS-E");

// CCAR prefix → CAAC
console.log("\nCCAR prefix detection:");
assertEqual(inferAgency({document: "CCAR-33-R2"}), "CAAC", "CCAR-33-R2 → CAAC");
assertEqual(inferAgency({document: "CCAR-25-R4"}), "CAAC", "CCAR-25-R4 → CAAC");
assertEqual(inferAgency({document: "CCAR-33-R2_chapters/33.65"}), "CAAC", "CCAR-33-R2_chapters/33.65 → CAAC");
assertEqual(inferAgency({document: "caac-ccar-33-r2"}), "CAAC", "caac-ccar-33-r2 (prefix-stripped) → CAAC");
assertEqual(inferAgency({document: "easa-cs-e"}), "EASA", "easa-cs-e (prefix-stripped) → EASA");
assertEqual(inferAgency({document: "faa-far-25"}), "FAA", "faa-far-25 (prefix-stripped) → FAA");

// AP prefix → CAAC
console.log("\nAP prefix detection:");
assertEqual(inferAgency({document: "AP-21"}), "CAAC", "AP-21 → CAAC");
assertEqual(inferAgency({document: "ap-21"}), "CAAC", "lowercase ap-21 → CAAC");

// AC prefix → CAAC
console.log("\nAC prefix detection:");
assertEqual(inferAgency({document: "AC-33.70-1"}), "CAAC", "AC-33.70-1 → CAAC");
assertEqual(inferAgency({document: "ac-33"}), "CAAC", "lowercase ac-33 → CAAC");

// FAR prefix → FAA
console.log("\nFAR prefix detection:");
assertEqual(inferAgency({document: "FAR-25"}), "FAA", "FAR-25 → FAA");
assertEqual(inferAgency({document: "FAR-33"}), "FAA", "FAR-33 → FAA");
assertEqual(inferAgency({document: "far-25"}), "FAA", "lowercase far-25 → FAA");

// CS prefix → EASA
console.log("\nCS prefix detection:");
assertEqual(inferAgency({document: "CS-E"}), "EASA", "CS-E → EASA");
assertEqual(inferAgency({document: "CS-25"}), "EASA", "CS-25 → EASA");
assertEqual(inferAgency({document: "cs-e"}), "EASA", "lowercase cs-e → EASA");

// ID field fallback (when no document field)
console.log("\nID field fallback:");
assertEqual(inferAgency({id: "CCAR-33-R2_node1"}), "CAAC", "id=CCAR-33-R2_node1 → CAAC");
assertEqual(inferAgency({id: "FAR-33_node2"}), "FAA", "id=FAR-33_node2 → FAA");
assertEqual(inferAgency({id: "CS-E_node3"}), "EASA", "id=CS-E_node3 → EASA");

// No match → empty string
console.log("\nNo match (edge cases):");
assertEqual(inferAgency({id: "node-1"}), "", "generic node-id returns empty");
assertEqual(inferAgency({document: "GENERIC-DOC"}), "", "generic document returns empty");
assertEqual(inferAgency({document: ""}), "", "empty document returns empty");
assertEqual(inferAgency({}), "", "empty node returns empty");
assertEqual(inferAgency({group: ""}), "", "empty group returns empty");
assertEqual(inferAgency({group: "OTHER"}), "", "unknown group returns empty");

// Summary
console.log(`\n=== Results: ${passed} passed, ${failed} failed ===`);
if (failed > 0) {
    process.exit(1);
}
