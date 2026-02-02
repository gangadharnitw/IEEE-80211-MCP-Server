-- IEEE 802.11 Database Schema
-- SQLite schema for storing extracted specification content

-- Specifications table (parent)
CREATE TABLE IF NOT EXISTS specifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_id TEXT UNIQUE NOT NULL,
    spec_name TEXT,
    source_pdf TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    page_range_start INTEGER,
    page_range_end INTEGER
);

-- Sections table
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_id TEXT NOT NULL,
    section_number TEXT,
    section_title TEXT NOT NULL,
    level INTEGER,
    page INTEGER,
    text TEXT,
    FOREIGN KEY (spec_id) REFERENCES specifications(spec_id)
);

-- Tables table (with section context)
CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_id TEXT NOT NULL,
    table_number TEXT,
    caption TEXT,
    page INTEGER,
    content_markdown TEXT,
    section_number TEXT,
    level INTEGER,
    FOREIGN KEY (spec_id) REFERENCES specifications(spec_id)
);

-- Figures table (with section context)
CREATE TABLE IF NOT EXISTS figures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_id TEXT NOT NULL,
    figure_number TEXT,
    caption TEXT,
    page INTEGER,
    image_path TEXT,
    image_base64 TEXT,
    section_number TEXT,
    level INTEGER,
    FOREIGN KEY (spec_id) REFERENCES specifications(spec_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sections_spec ON sections(spec_id);
CREATE INDEX IF NOT EXISTS idx_sections_number ON sections(section_number);
CREATE INDEX IF NOT EXISTS idx_sections_page ON sections(page);
CREATE INDEX IF NOT EXISTS idx_tables_spec ON tables(spec_id);
CREATE INDEX IF NOT EXISTS idx_tables_number ON tables(table_number);
CREATE INDEX IF NOT EXISTS idx_tables_section ON tables(section_number);
CREATE INDEX IF NOT EXISTS idx_figures_spec ON figures(spec_id);
CREATE INDEX IF NOT EXISTS idx_figures_number ON figures(figure_number);
CREATE INDEX IF NOT EXISTS idx_figures_section ON figures(section_number);
