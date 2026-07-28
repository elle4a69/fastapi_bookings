const { chromium } = require('playwright');

(async () => {
  console.log('Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Intercept requests and responses to monitor the location updates
  let putRequestPayload = null;
  let putResponsePayload = null;

  page.on('request', request => {
    if (request.url().includes('/api/admin/locations/') && request.method() === 'PUT') {
      console.log('\n[API Request] PUT', request.url());
      console.log('[API Request Payload]', request.postData());
      try {
        putRequestPayload = JSON.parse(request.postData());
      } catch (e) {
        console.error('Failed to parse request data:', e);
      }
    }
  });

  page.on('response', async response => {
    if (response.url().includes('/api/admin/locations/') && response.request().method() === 'PUT') {
      console.log('[API Response Status]', response.status());
      try {
        const text = await response.text();
        console.log('[API Response Payload]', text);
        putResponsePayload = JSON.parse(text);
      } catch (e) {
        console.error('Failed to parse response data:', e);
      }
    }
  });

  try {
    console.log('Navigating to Locations page...');
    await page.goto('http://localhost:7070/admin/catalog/locations');
    await page.waitForLoadState('networkidle');

    // 1. Select Location Branch 1 from the list
    console.log('Selecting "Location Branch 1"...');
    const branch1Button = page.locator('button:has-text("Location Branch 1")');
    await branch1Button.waitFor({ state: 'visible', timeout: 5000 });
    await branch1Button.click();

    // Wait for the detail pane to populate
    console.log('Waiting for Location details to load...');
    await page.waitForTimeout(1000);

    // 2. Expand "Location Providers" accordion
    console.log('Expanding "Location Providers" accordion...');
    const providersAccordion = page.getByRole('button', { name: 'Location Providers' });
    await providersAccordion.waitFor({ state: 'visible', timeout: 5000 });
    await providersAccordion.click();
    await page.waitForTimeout(500);

    // 3. Toggle a provider (check "Demo Provider 1")
    console.log('Locating provider checkbox for "Demo Provider 1"...');
    const providerLabel = page.locator('label:has-text("Demo Provider 1")');
    await providerLabel.waitFor({ state: 'visible', timeout: 5000 });
    
    // Find the associated checkbox/button to inspect its check state
    const checkboxId = await providerLabel.getAttribute('for');
    console.log(`Provider checkbox ID: ${checkboxId}`);
    const checkbox = page.locator(`#${checkboxId}`);

    const isCheckedBefore = await checkbox.getAttribute('aria-checked') === 'true';
    console.log(`Checkbox is checked before click: ${isCheckedBefore}`);

    // If it's already checked, we want to toggle it or make sure it's checked.
    // Let's click it to check it if it was not checked.
    if (!isCheckedBefore) {
      console.log('Clicking provider label to CHECK...');
      await providerLabel.click();
      // Wait for any network requests to settle
      await page.waitForTimeout(1500);
    } else {
      console.log('Checkbox is already checked, toggling it off and on to force an update...');
      await providerLabel.click();
      await page.waitForTimeout(1500);
      await providerLabel.click();
      await page.waitForTimeout(1500);
    }

    const isCheckedAfter = await checkbox.getAttribute('aria-checked') === 'true';
    console.log(`Checkbox is checked after click: ${isCheckedAfter}`);
    if (!isCheckedAfter) {
      throw new Error('Failed to check the provider checkbox!');
    }

    // Verify PUT request occurred and is correct
    if (!putRequestPayload) {
      throw new Error('No PUT request detected on checkbox toggle!');
    }
    console.log('Validating PUT payload provider_ids:', putRequestPayload.provider_ids);
    
    if (!putResponsePayload || !putResponsePayload.data) {
      throw new Error('No valid response payload returned from PUT request!');
    }
    console.log('Validating PUT response provider_ids:', putResponsePayload.data.provider_ids);

    // 4. Switch to Location Branch 2
    console.log('Switching to "Location Branch 2"...');
    const branch2Button = page.locator('button:has-text("Location Branch 2")');
    await branch2Button.click();
    await page.waitForTimeout(1000);

    // 5. Switch back to Location Branch 1
    console.log('Switching back to "Location Branch 1"...');
    await branch1Button.click();
    await page.waitForTimeout(1000);

    // 6. Assert that "Demo Provider 1" checkbox is still checked
    console.log('Checking "Demo Provider 1" state after switching back...');
    const isCheckedFinal = await checkbox.getAttribute('aria-checked') === 'true';
    console.log(`Final checkbox state: ${isCheckedFinal}`);

    if (!isCheckedFinal) {
      throw new Error('Assertion Failed: "Demo Provider 1" was not persisted and is UNCHECKED after switching back!');
    }

    console.log('\nSUCCESS: Test passed! Relationship persistence is working correctly.');
  } catch (error) {
    console.error('\nFAILURE:', error.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
