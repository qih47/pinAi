import asyncio
import json
from playwright.async_api import async_playwright


async def crawl_pindad_v12_final():
    base_url = "https://www.pindad.com"
    output_file = "pindad_full_data.json"
    final_datalinks = []
    global_id = 1
    homepage_master_urls = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        # --- STEP 1: MAPPING NAVIGASI ---
        print(f"🌐 Step 1: Mapping Navigasi (Logic v11)...")
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        except:
            print("⚠️ Homepage lambat, mencoba tetap mapping...")

        nav_structure = await page.evaluate("""() => {
            const results = [];
            const navElements = document.querySelectorAll('header nav, .header nav, ul.js-dropdown');
            navElements.forEach(nav => {
                const topItems = nav.querySelectorAll(':scope > li');
                topItems.forEach(li => {
                    const fatherA = li.querySelector('a');
                    if (!fatherA) return;
                    const fatherTitle = fatherA.innerText.trim().toUpperCase() || "MENU";
                    const subMenu = li.querySelector('ul');
                    if (!subMenu) {
                        results.push({ category: fatherTitle, sub_category: fatherTitle, url: fatherA.href.split('#')[0].replace(/\/$/, "") });
                    } else {
                        const children = subMenu.querySelectorAll(':scope > li');
                        children.forEach(childLi => {
                            const childA = childLi.querySelector('a');
                            if (!childA) return;
                            const childTitle = childA.innerText.trim().toUpperCase();
                            const grandMenu = childLi.querySelector('ul');
                            if (!grandMenu) {
                                results.push({ category: fatherTitle, sub_category: childTitle, url: childA.href.split('#')[0].replace(/\/$/, "") });
                            } else {
                                const grandchildren = grandMenu.querySelectorAll('li a');
                                grandchildren.forEach(gA => {
                                    results.push({ category: fatherTitle, sub_category: childTitle + " > " + gA.innerText.trim().toUpperCase(), url: gA.href.split('#')[0].replace(/\/$/, "") });
                                });
                            }
                        });
                    }
                });
            });
            return results;
        }""")

        for entry in nav_structure:
            u = entry["url"]
            if u and "pindad.com" in u and "javascript" not in u:
                if u not in homepage_master_urls:
                    homepage_master_urls.add(u)
                    final_datalinks.append(
                        {
                            "id": global_id,
                            "category_name": entry["category"],
                            "sub_category": entry["sub_category"],
                            "isPrimary": "Primary",
                            "label": entry["sub_category"].split(" > ")[-1],
                            "url": u,
                            "content": "",
                        }
                    )
                    global_id += 1

        print(f"✅ Step 1 Beres: {len(final_datalinks)} link Primary.")

        # --- STEP 2: SCAN SUBLINK ---
        print(f"🔎 Step 2: Scanning Sublinks...")
        primaries = [
            d
            for d in final_datalinks
            if d["url"] != base_url and "home" not in d["url"]
        ]

        for pri in primaries:
            print(f"   Searching in: {pri['label']}...", end=" ", flush=True)
            try:
                # Naikin dikit timeout dan pake domcontentloaded
                await page.goto(
                    pri["url"], wait_until="domcontentloaded", timeout=30000
                )
                await asyncio.sleep(1)  # Kasih jeda biar server gak pusing

                master_list = list(homepage_master_urls)
                content_links = await page.evaluate(
                    """(master) => {
                    const results = [];
                    const allLinks = Array.from(document.querySelectorAll('a[href]'));
                    allLinks.forEach(a => {
                        const url = a.href.split('#')[0].replace(/\/$/, "");
                        const label = a.innerText.trim();
                        if (url.startsWith('https://www.pindad.com') && label.length > 2 && !master.includes(url)) {
                            // Filter biar gak ngambil link di navbar/footer/nav
                            if (!a.closest('header') && !a.closest('footer') && !a.closest('nav') && !a.closest('.menu')) {
                                results.push({ label, url });
                            }
                        }
                    });
                    return results;
                }""",
                    master_list,
                )

                sub_added = 0
                for cl in content_links:
                    if cl["url"] not in homepage_master_urls:
                        final_datalinks.append(
                            {
                                "id": global_id,
                                "category_name": pri["category_name"],
                                "sub_category": pri["sub_category"],
                                "isPrimary": "Sublink",
                                "label": cl["label"],
                                "url": cl["url"],
                                "content": "",
                            }
                        )
                        global_id += 1
                        homepage_master_urls.add(cl["url"])
                        sub_added += 1
                print(f"dapet {sub_added} link.")
            except Exception:
                print("⚠️ Skip (Timeout/Error).")

        # --- STEP 3: AMBIL KONTEN (DENGAN EKSTRAKSI LENGKAP) ---
        print(f"\n📝 Step 3: Ambil Konten (Total {len(final_datalinks)} link)...")

        for i, item in enumerate(final_datalinks):
            print(
                f"   [{i + 1}/{len(final_datalinks)}] Extracting: {item['url']}",
                end="\r",
            )
            try:
                await page.goto(item["url"], wait_until="networkidle", timeout=30000)

                # ✅ EKSTRAKSI TEKS LENGKAP (seperti extract_weapon_full.py)
                item["content"] = await page.evaluate("""() => {
                    // Hapus hanya elemen yang benar-benar tidak perlu
                    const toRemove = [
                        'script', 'style', 'header', 'footer',
                        '.topbar', '.copyright', '.back-to-top',
                        '.social-icons', '.share-buttons', '.menu'
                    ];
                    toRemove.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => el.remove());
                    });

                    // Ambil SEMUA teks dari body
                    let fullText = '';
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    let node;
                    while (node = walker.nextNode()) {
                        const text = node.textContent.trim();
                        if (text && text.length > 1) {
                            fullText += text + '\\n';
                        }
                    }
                    return fullText.trim();
                }""")
            except Exception as e:
                item["content"] = f"ERROR: {str(e)}"

            # Auto-save berkala
            if (i + 1) % 10 == 0:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {"total": len(final_datalinks), "data": final_datalinks},
                        f,
                        indent=4,
                        ensure_ascii=False,
                    )

        # Final Save
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                {"total": len(final_datalinks), "data": final_datalinks},
                f,
                indent=4,
                ensure_ascii=False,
            )

    print(f"\n🚀 BERES! Cek file: {output_file}")


if __name__ == "__main__":
    asyncio.run(crawl_pindad_v12_final())
