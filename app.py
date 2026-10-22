import json
import streamlit as st
from collector import collect_site, TargetValidationError
from passive_recon import find_subdomains_passive
from database import initialize_database, save_snapshot, get_snapshots
from tracker import compare_with_previous
from analyzer import create_report

st.set_page_config(page_title="Lightweight OSINT MVP", page_icon="🔎", layout="wide")
initialize_database()
st.title("🔎 Lightweight OSINT Target Profiler Tracker")
st.caption("MVP 8-layer untuk aset web publik yang Anda miliki atau berwenang analisis.")

with st.sidebar:
    st.header("Batas penggunaan")
    st.write("Crawl dibatasi ke host yang sama, maksimum 15 halaman. Subdomain dicari pasif dari Certificate Transparency; tidak dipindai.")
    st.warning("Masukkan hanya domain milik Anda atau yang Anda punya izin tertulis untuk dianalisis.")
    st.write("AI: " + ("API key tersedia" if __import__("os").getenv("OPENAI_API_KEY") else "ringkasan lokal; atur OPENAI_API_KEY untuk AI"))

target = st.text_input("URL HTTPS target", "https://example.com")
authorized = st.checkbox("Saya pemilik aset ini atau memiliki izin untuk menganalisisnya.")
run = st.button("Jalankan analisis 8 layer", type="primary", use_container_width=True)

if run:
    if not authorized:
        st.error("Konfirmasi otorisasi diperlukan sebelum analisis.")
    else:
        try:
            with st.spinner("Mengumpulkan halaman dan petunjuk publik..."):
                profile = collect_site(target)
                subdomains = find_subdomains_passive(profile["target"])
                previous_rows = get_snapshots(profile["target"], limit=1)
                comparison = compare_with_previous(profile, previous_rows[0] if previous_rows else None)
                save_snapshot(profile["target"], profile)
                report = create_report(profile, comparison, subdomains)
                bundle = {"profile": profile, "subdomains": subdomains, "comparison": comparison, "report": report}
                st.session_state["latest_bundle"] = bundle

            st.success("Analisis selesai.")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Halaman ditemukan", profile["pages_scanned"])
            c2.metric("Petunjuk teknologi", len(profile["technology_hints"]))
            c3.metric("Subdomain pasif", subdomains["count"])
            c4.metric("Perubahan", len(comparison["differences"]))
            tabs = st.tabs(["Ringkasan", "Halaman & tautan", "Subdomain", "Teknologi", "Perubahan", "JSON"])
            with tabs[0]:
                st.write(report.get("ai_summary", report["summary"]))
                st.write("**Mode laporan:**", report["mode"])
                for item in report["findings"]:
                    st.write("- " + item)
                for item in report["limitations"]:
                    st.caption("Batasan: " + item)
                if report.get("ai_error"):
                    st.warning("AI tidak tersedia pada percobaan ini; ringkasan lokal digunakan.")
            with tabs[1]:
                st.dataframe([{"URL": p["url"], "HTTP": p["status_code"], "Judul": p["title"],
                               "Deskripsi": p["description"]} for p in profile["pages"]], use_container_width=True)
                st.caption("Crawl hanya mengunjungi URL HTTPS pada host yang sama.")
            with tabs[2]:
                st.write(subdomains.get("note", ""))
                if subdomains.get("error"):
                    st.warning("Lookup Certificate Transparency tidak berhasil.")
                st.dataframe([{"Subdomain": s} for s in subdomains["subdomains"]], use_container_width=True)
            with tabs[3]:
                st.write("Petunjuk teknologi bukan bukti pasti.")
                st.dataframe(profile["technology_hints"], use_container_width=True)
            with tabs[4]:
                if comparison["previous_exists"]:
                    st.json(comparison["differences"] or {"status": "Tidak ada perubahan"})
                else:
                    st.info("Ini snapshot pertama. Jalankan lagi nanti untuk membandingkan.")
            with tabs[5]:
                st.json(bundle)
            st.download_button("Unduh laporan JSON", json.dumps(bundle, ensure_ascii=False, indent=2),
                               file_name="osint_report.json", mime="application/json")
        except TargetValidationError as exc:
            st.error(str(exc))
        except Exception:
            st.error("Analisis gagal. Periksa URL/koneksi. Detail internal tidak ditampilkan.")

if st.button("Tampilkan riwayat snapshot"):
    try:
        rows = get_snapshots(target, limit=50)
        st.dataframe([{"Waktu UTC": r["collected_at"], "Target": r["target"],
                       "Judul": r["content"].get("title"), "Jumlah halaman": r["content"].get("pages_scanned")}
                      for r in rows], use_container_width=True)
    except Exception:
        st.error("Riwayat tidak dapat dimuat.")

st.divider()
st.markdown("""
**Peta 8 layer MVP**
1. DNS/public host validation (pengaman pengambilan).
2. HTTP status, content type, server headers.
3. HTML metadata, canonical, robots, Open Graph.
4. Crawl tautan internal satu host (maks. 15 halaman).
5. Subdomain pasif dari Certificate Transparency.
6. Petunjuk teknologi dari header/HTML.
7. Snapshot SQLite dan diff antar-run.
8. Ringkasan AI opsional via `OPENAI_API_KEY`, dengan fallback lokal.

**Deploy:** SQLite lokal cocok untuk demo satu instance; untuk hosting yang persisten, gunakan volume persisten atau database terkelola. Batasi akses dashboard dengan autentikasi sebelum dibuka ke publik.
""")
