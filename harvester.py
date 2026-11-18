TARGET_WEBSITES = [
    # Сайты-агрегаторы и блоги с ежедневными раздачами
    "https://v2rayse.com/en/free-v2ray",
    "https://v2ray-nodes.com/",
    "https://openproxylist.com/v2ray/",
    "https://shadowmere.xyz/",
    "https://freefq.com/",
    "https://nodefree.org/",
    "https://clashnode.com/",
    "https://v2rayshare.com/",
    "https://oneclash.cc/",
    "https://mibei77.com/",
    # Публичные Telegram-каналы (веб-зеркало t.me/s/)
    "https://t.me/s/vless_vmess",
    "https://t.me/s/V2rayNG_Fast",
    "https://t.me/s/ConfigsHUB",
    "https://t.me/s/PrivateVPNs",
    "https://t.me/s/v2ray_outlineir",
    "https://t.me/s/ShadowProxy66",
    "https://t.me/s/proxy_shadosocks",
    "https://t.me/s/Reality_Vless",
    "https://t.me/s/free4allVPN",
    "https://t.me/s/V2rayCollectorDonate",
    "https://t.me/s/v2rayng_vpnrog",
    "https://t.me/s/v2ray_free_conf",
    "https://t.me/s/VlessConfig",
    "https://t.me/s/v2rayngvpn",
    "https://t.me/s/ConfigsHUB2",
    "https://t.me/s/OutlineVpnOfficial",
    "https://t.me/s/v2ray_configs_pool",
    "https://t.me/s/DirectVPN",
    "https://t.me/s/FreeV2rays",
    "https://t.me/s/v2ray_alpha",
    "https://t.me/s/DailyV2RY",
    "https://t.me/s/V2RayRootFree",
    "https://t.me/s/proxy_kafee",
    "https://t.me/s/v2ray_sub",
]


async def discover_fresh_github_sources(session: aiohttp.ClientSession) -> list[str]:
    """Максимальный поиск по GitHub: находит свежие репы и вскрывает их файловое дерево (Git Trees)"""
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "TheLastVPN-MaxHarvester"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    queries = [
        "vless reality subscription",
        "v2ray-configs sub txt",
        "free vless configs",
        "xray subscription base64",
        "v2ray collector vless",
        "Splitted-By-Protocol vless",
        "telegram-configs-collector",
        "free-v2ray-configs",
    ]
    repos_to_scan = {}

    for q in queries:
        api_url = f"https://api.github.com/search/repositories?q={urllib.request.quote(q)}&sort=updated&order=desc&per_page=25"
        try:
            async with session.get(api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                for repo in data.get("items", []):
                    full_name = repo.get("full_name")
                    branch = repo.get("default_branch", "main")
                    if full_name and full_name not in repos_to_scan:
                        repos_to_scan[full_name] = branch
        except Exception:
            pass

    discovered = set()
    tree_sem = asyncio.Semaphore(15)

    async def scan_repo_tree(full_name: str, branch: str):
        async with tree_sem:
            tree_url = f"https://api.github.com/repos/{full_name}/git/trees/{branch}?recursive=1"
            try:
                async with session.get(tree_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        return
                    tree_data = await resp.json()
                    for item in tree_data.get("tree", []):
                        if item.get("type") != "blob":
                            continue
                        path = item.get("path", "")
                        low = path.lower()
                        # Берём файлы, похожие на подписки, и отсекаем мусор вроде .py/.md/.yml/.png
                        if any(low.endswith(bad) for bad in [".py", ".sh", ".yml", ".yaml", ".json", ".md", ".png", ".jpg", ".js", ".go"]):
                            continue
                        if any(k in low for k in ["vless", "reality", "sub", "mix", "config", "all", "node", "free", "merged"]):
                            raw_link = f"https://raw.githubusercontent.com/{full_name}/{branch}/{path}"
                            discovered.add(raw_link)
            except Exception:
                pass

    # Сканируем до 80 самых свежих репозиториев
    await asyncio.gather(*(scan_repo_tree(fn, br) for fn, br in list(repos_to_scan.items())[:80]))
    print(f"[Глубокая разведка GitHub] Вскрыто реп: {len(repos_to_scan)} | Найдено файлов-подписок: {len(discovered)}")
    return list(discovered)


async def scrape_sites_and_telegram(session: aiohttp.ClientSession, sem: asyncio.Semaphore) -> set[str]:
    """Парсит сайты-агрегаторы, свежие посты блогов и 25+ Telegram-каналов"""
    found_uris = set()
    extra_sub_urls = set()

    pages = await asyncio.gather(*(fetch_source(session, site, sem) for site in TARGET_WEBSITES))

    for site, html in zip(TARGET_WEBSITES, pages):
        if not html:
            continue

        clean_html = html.replace("&amp;", "&")
        for uri in re.findall(r'(?:vless|vmess|trojan)://[^\s<>"\'`]+', clean_html):
            found_uris.add(uri.strip())

        soup = BeautifulSoup(clean_html, "html.parser")
        base_domain = "/".join(site.split("/")[:3])
        post_links = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("/"):
                href = base_domain + href
            if not href.startswith("http"):
                continue

            if any(ext in href.lower() for ext in [".txt", "/sub", "b64sub", "export", "v2ray"]):
                if "t.me/" not in href:
                    extra_sub_urls.add(href)
            elif any(k in site for k in ["nodefree", "clashnode", "freefq", "v2rayshare", "oneclash", "mibei"]) and any(
                y in href for y in ["/2026/", "/post/", "/free-", ".html"]
            ):
                if href not in post_links and href != site:
                    post_links.append(href)

        # Заходим в первые 5 свежих постов каждого сайта-блога
        for post_url in post_links[:5]:
            post_html = await fetch_source(session, post_url, sem)
            if post_html:
                post_clean = post_html.replace("&amp;", "&")
                for uri in re.findall(r'(?:vless|vmess|trojan)://[^\s<>"\'`]+', post_clean):
                    found_uris.add(uri.strip())
                for sub_link in re.findall(r'https?://[^\s<>"\'`]+\.txt', post_clean):
                    extra_sub_urls.add(sub_link.strip())

    if extra_sub_urls:
        sub_pages = await asyncio.gather(*(fetch_source(session, u, sem) for u in list(extra_sub_urls)[:80]))
        for content in sub_pages:
            if not content:
                continue
            text = content
            if "://" not in content[:100]:
                try:
                    text = decode_b64(content)
                except Exception:
                    pass
            for line in text.splitlines():
                line = line.strip()
                if line.startswith(("vless://", "vmess://", "trojan://")):
                    found_uris.add(line)

    print(f"[Краулер сайтов + TG] Вытащено прямых нод: {len(found_uris)} | Подписок с сайтов: {len(extra_sub_urls)}")
    return found_uris


async def harvest_raw_nodes() -> list[str]:
    saved_urls = []
    if os.path.exists(SOURCES_FILE):
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            saved_urls = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]

    sem = asyncio.Semaphore(40)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    raw_uris = set()
    alive_urls = []

    async with aiohttp.ClientSession(headers=headers) as session:
        fresh_urls = await discover_fresh_github_sources(session)
        web_and_tg_uris = await scrape_sites_and_telegram(session, sem)
        raw_uris.update(web_and_tg_uris)

        # Ограничиваем общий прогон до 600 источников за запуск, чтобы не упереться в таймаут
        all_candidate_urls = list(dict.fromkeys(saved_urls + fresh_urls))[:600]

        async def check_and_fetch(u: str):
            content = await fetch_source(session, u, sem)
            if content and len(content) > 50:
                alive_urls.append(u)
            return content

        pages = await asyncio.gather(*(check_and_fetch(u) for u in all_candidate_urls))

    # Храним до 500 только 100% рабочих источников в sources.txt
    if alive_urls:
        with open(SOURCES_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(alive_urls[:500]) + "\n")
        print(f"[Самоочистка] В sources.txt обновлено живых источников: {len(alive_urls[:500])}")

    for content in pages:
        if not content:
            continue
        text = content
        if "://" not in content[:100]:
            try:
                text = decode_b64(content)
            except Exception:
                pass
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(("vless://", "vmess://", "trojan://")):
                raw_uris.add(line)

    reality = [u for u in raw_uris if u.startswith("vless://") and "security=reality" in u]
    others = [u for u in raw_uris if u not in reality]
    random.shuffle(reality)
    random.shuffle(others)
    combined = reality + others
    print(f"[Пылесос MAX] Собрано уникальных нод: {len(combined)} (из них VLESS+Reality: {len(reality)})")
    return combined[:6000]
