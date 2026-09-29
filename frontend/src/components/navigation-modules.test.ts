// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from "node:test";
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from "node:assert/strict";
import { isKeyActive, filterNavigationByModules, navigation } from "./navigation.ts";

test("isKeyActive resolves canonical and alias module keys accurately", () => {
  // Test multiple_providers alias compatibility
  assert.equal(isKeyActive("multiple_providers", new Set(["multiple_providers"])), true);
  assert.equal(isKeyActive("multiple_providers", new Set(["providers"])), true);
  assert.equal(isKeyActive("providers", new Set(["multiple_providers"])), true);
  assert.equal(isKeyActive("multiple_providers", new Set(["locations"])), false);

  // Test addons alias compatibility
  assert.equal(isKeyActive("addons", new Set(["addons"])), true);
  assert.equal(isKeyActive("addons", new Set(["packages"])), true);
  assert.equal(isKeyActive("packages", new Set(["addons"])), true);
  assert.equal(isKeyActive("addons", new Set(["products"])), false);

  // Test standard keys
  assert.equal(isKeyActive("categories", new Set(["categories"])), true);
  assert.equal(isKeyActive("categories", new Set(["products"])), false);
  assert.equal(isKeyActive("products", new Set(["products"])), true);
  assert.equal(isKeyActive("locations", new Set(["locations"])), true);
});

test("filterNavigationByModules cleanly removes disabled modules from sidebar navigation", () => {
  // Minimal enabled set: only core catalog, disabling providers, categories, addons, products
  const enabledModules = ["locations"];
  const filtered = filterNavigationByModules(navigation, enabledModules);

  // Extract all item titles in catalog
  const catalogSection = filtered.find(s => s.label === "Catalog");
  assert.ok(catalogSection, "Catalog section should exist");

  const titles = catalogSection!.items.map(i => i.title);
  assert.ok(titles.includes("Locations"), "Locations should be present");
  assert.ok(titles.includes("Services"), "Services should be present");
  assert.ok(!titles.includes("Categories"), "Categories must be removed");
  assert.ok(!titles.includes("Providers"), "Providers must be removed");
  assert.ok(!titles.includes("Add-ons"), "Add-ons must be removed");
  assert.ok(!titles.includes("Products"), "Products must be removed");

  const operationsSection = filtered.find(s => s.label === "Operations");
  assert.ok(operationsSection);
  const opTitles = operationsSection!.items.map(i => i.title);
  assert.ok(!opTitles.includes("Relationships"), "Multi-provider Relationships must be removed");
});

test("filterNavigationByModules preserves all items when all modules are enabled", () => {
  const allModules = ["multiple_providers", "locations", "categories", "products", "addons", "relationship_matrix", "sms", "scheduling"];
  const filtered = filterNavigationByModules(navigation, allModules);

  const catalogSection = filtered.find(s => s.label === "Catalog");
  assert.ok(catalogSection);

  const titles = catalogSection!.items.map(i => i.title);
  assert.ok(titles.includes("Categories"));
  assert.ok(titles.includes("Locations"));
  assert.ok(titles.includes("Services"));
  assert.ok(titles.includes("Providers"));
  assert.ok(titles.includes("Add-ons"));
  assert.ok(titles.includes("Products"));

  const operationsSection = filtered.find(s => s.label === "Operations");
  assert.ok(operationsSection);
  const opTitles = operationsSection!.items.map(i => i.title);
  assert.ok(opTitles.includes("Relationships"));
});

test("relationship_matrix strictly requires multiple_providers to be enabled", () => {
  // 1. Both enabled -> active
  assert.equal(
    isKeyActive("relationship_matrix", new Set(["relationship_matrix", "multiple_providers"])),
    true
  );
  assert.equal(
    isKeyActive("relationships_matrix", new Set(["relationships_matrix", "providers"])),
    true
  );

  // 2. relationship_matrix enabled but multiple_providers disabled -> inactive (killed!)
  assert.equal(
    isKeyActive("relationship_matrix", new Set(["relationship_matrix", "locations"])),
    false
  );
  assert.equal(
    isKeyActive("relationship_matrix", new Set(["relationship_matrix"])),
    false
  );

  // 3. multiple_providers enabled but relationship_matrix disabled -> inactive
  assert.equal(
    isKeyActive("relationship_matrix", new Set(["multiple_providers"])),
    false
  );

  // 4. Navigation filtering: with relationship_matrix enabled without multiple_providers, Relationships is hidden
  const singleProviderWithMatrix = filterNavigationByModules(navigation, ["relationship_matrix", "locations"]);
  const ops1 = singleProviderWithMatrix.find(s => s.label === "Operations");
  assert.ok(ops1);
  const titles1 = ops1!.items.map(i => i.title);
  assert.ok(!titles1.includes("Relationships"), "Relationships must be hidden without multiple_providers");

  // 5. Navigation filtering: with both enabled, Relationships and all children are visible
  const multiProviderWithMatrix = filterNavigationByModules(navigation, ["relationship_matrix", "multiple_providers"]);
  const ops2 = multiProviderWithMatrix.find(s => s.label === "Operations");
  assert.ok(ops2);
  const relItem = ops2!.items.find(i => i.title === "Relationships");
  assert.ok(relItem, "Relationships must be visible when both modules are enabled");
  assert.equal(relItem!.children?.length, 3, "All 3 child views must be present");
});
