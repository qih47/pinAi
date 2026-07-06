import asyncio
import aiomysql
import asyncpg
import json

async def check():
    # Peraturan DB (MySQL)
    try:
        conn_mysql = await aiomysql.connect(host='192.168.11.55', port=3306, user='qisthi', password='q1sthi', db='qa_peraturan_db')
        async with conn_mysql.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SHOW TABLES")
            tables = await cur.fetchall()
            print("--- MYSQL TABLES ---")
            print(tables)
            
            await cur.execute("DESCRIBE berita")
            print("--- BERITA SCHEMA ---")
            for row in await cur.fetchall(): print(row)
            
            await cur.execute("SELECT * FROM berita LIMIT 1")
            print("--- BERITA SAMPLE ---")
            for row in await cur.fetchall(): print(row)
            
            await cur.execute("DESCRIBE kategori")
            print("--- KATEGORI SCHEMA ---")
            for row in await cur.fetchall(): print(row)
            
            await cur.execute("SELECT * FROM kategori LIMIT 1")
            print("--- KATEGORI SAMPLE ---")
            for row in await cur.fetchall(): print(row)
            
        conn_mysql.close()
    except Exception as e:
        print("MySQL Error:", e)

    # RAG DB (Postgres)
    try:
        conn_pg = await asyncpg.connect(host='localhost', user='pindadai', password='Pindad123!', database='ragdb')
        
        print("\n--- RAGDB DOKUMEN SCHEMA ---")
        rows = await conn_pg.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'dokumen'")
        for row in rows: print(row)
        
        print("\n--- RAGDB DOKUMEN_SECTION SCHEMA ---")
        rows = await conn_pg.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'dokumen_section'")
        for row in rows: print(row)
        
        print("\n--- RAGDB DOKUMEN_CHUNK SCHEMA ---")
        rows = await conn_pg.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'dokumen_chunk'")
        for row in rows: print(row)
        
        await conn_pg.close()
    except Exception as e:
        print("PG Error:", e)

asyncio.run(check())
