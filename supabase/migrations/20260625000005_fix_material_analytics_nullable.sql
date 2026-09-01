-- Fix: Hacer material_id nullable en material_analytics
-- Permite registrar analytics sin vincular a un material existente
ALTER TABLE material_analytics ALTER COLUMN material_id DROP NOT NULL;
