/**
 * Instrumentos de autovaloración (mismos ítems y puntajes en la app y en el
 * formulario que completa el paciente desde su enlace).
 * - VHI-10 oficial: 10 ítems de 0 a 4 (total 0–40).
 * - Cuestionario de Riesgo Vocal 2026: 69 ítems de 0 a 3 (total 0–207).
 */
export const RIESGO_VOCAL_2026 = {
  name: 'Cuestionario de Riesgo Vocal (69 ítems — Manual Edición 2026)',
  dimensions: [
    {
      categoria: "Sección 1 — Hábitos Vocales (32 ítems)",
      items: [
        { key: "A1", label: "1. ¿Habla fuerte?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A2", label: "2. ¿Es muy conversador?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A3", label: "3. ¿Hace uso prolongado de la voz?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A4", label: "4. ¿Habla en registro gruñidor (ronco)?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A5", label: "5. ¿Habla susurrando?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A6", label: "6. ¿Utiliza una articulación cerrada?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A7", label: "7. ¿Hace esfuerzo al hablar?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A8", label: "8. ¿Habla con poco aire?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A9", label: "9. ¿Hace aspiraciones ruidosas al hablar?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A10", label: "10. ¿Utiliza el tipo respiratorio costal superior durante la fonación?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A11", label: "11. ¿Llega sin aire al final de la frase?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A12", label: "12. ¿Habla rápido, con pocas pausas?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A13", label: "13. ¿Habla al mismo tiempo que los demás?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A14", label: "14. ¿Habla mucho por teléfono?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A15", label: "15. ¿Habla mucho al aire libre?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A16", label: "16. ¿Habla mucho en ambientes ruidosos?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A17", label: "17. ¿Carraspea en forma habitual?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A18", label: "18. ¿Ríe en reversión de la fonación?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A19", label: "19. ¿Grita con frecuencia?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A20", label: "20. ¿Grita en forma repentina y violenta?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A21", label: "21. ¿Imita voces?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A22", label: "22. ¿Canta covers?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A23", label: "23. ¿Canta mientras ejecuta instrumentos musicales?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A24", label: "24. ¿Imita ruidos o sonidos?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A25", label: "25. ¿Habla mientras su cuerpo adopta múltiples posturas?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A26", label: "26. ¿Usa la voz en forma habitual a pesar de estar cursando procesos respiratorios patológicos?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A27", label: "27. ¿Usa la voz luego de una ingesta abundante?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A28", label: "28. ¿Utiliza la voz después de exposiciones solares?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A29", label: "29. ¿Hace uso intenso de la voz matinal?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A30", label: "30. ¿Usa la voz cuando su interlocutor está a distancia?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A31", label: "31. ¿Practica deportes en los cuales utiliza la voz?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "A32", label: "32. ¿Integra grupos religiosos que exigen gran uso de la voz?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" }
      ]
    },
    {
      categoria: "Sección 2 — Estado Emocional (7 ítems)",
      items: [
        { key: "B1", label: "1. ¿Tiene preocupaciones económicas?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "B2", label: "2. ¿Tiene conflictos afectivos de orden personal o familiar?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "B3", label: "3. ¿Trabaja en situaciones conflictivas?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "B4", label: "4. ¿Es emocionalmente hiperreactivo?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "B5", label: "5. ¿Es emocionalmente reprimido?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "B6", label: "6. ¿Tiene un temperamento dominante y agresivo?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "B7", label: "7. ¿Se siente afectado por los problemas de los otros?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" }
      ]
    },
    {
      categoria: "Sección 3 — Condiciones Biológicas Desfavorables (12 ítems)",
      items: [
        { key: "C1", label: "1. ¿Padece alguna afección que disminuya su capacidad respiratoria?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C2", label: "2. ¿Es respirador bucal?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C3", label: "3. ¿Sufre procesos infecciosos o alérgicos en vías aéreas?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C4", label: "4. ¿Tiene tos?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C5", label: "5. ¿Tiene problemas auditivos?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C6", label: "6. ¿Tiene RGE o acidez gástrica?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C7", label: "7. ¿Es estreñido?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C8", label: "8. ¿Tiene problemas posturales?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C9", label: "9. ¿Siempre tuvo una voz poco clara?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C10", label: "10. ¿Se pone ronco con facilidad después de un esfuerzo vocal (excursión, fiestas, etc.)?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C11", label: "11. ¿Tiene antecedentes de ronquera en familiares?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "C12", label: "12. ¿Tiene rigidez corporal, falta de flexibilidad?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" }
      ]
    },
    {
      categoria: "Sección 4 — Condiciones Ambientales Desfavorables (7 ítems)",
      items: [
        { key: "D1", label: "1. ¿Permanece en ambientes con aire acondicionado o calefacción?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "D2", label: "2. ¿Permanece en ambientes con polvo, tiza, humedad o poca ventilación?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "D3", label: "3. ¿Comparte lugares con fumadores?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "D4", label: "4. ¿Vive en un ambiente familiar ruidoso?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "D5", label: "5. ¿Trabaja en un ambiente ruidoso?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "D6", label: "6. ¿Está expuesto a ruidos intensos?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "D7", label: "7. ¿Convive o trabaja con personas con problemas auditivos?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" }
      ]
    },
    {
      categoria: "Sección 5 — Hábitos de Vida (11 ítems)",
      items: [
        { key: "E1", label: "1. ¿Se expone a cambios bruscos de temperatura?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "E2", label: "2. ¿Duerme poco?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "E3", label: "3. ¿Ingiere poca agua? (Considerando que la cantidad necesaria para un profesional de la voz es de 3 litros diarios)", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "E4", label: "4. ¿Ingiere alimentos picantes?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "E5", label: "5. ¿Bebe café o té en exceso?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "E6", label: "6. ¿Ingiere bebidas heladas o muy calientes?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "E7", label: "7. ¿Consume drogas?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "E8", label: "8. ¿Ingiere alcohol?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "E9", label: "9. ¿Fuma tabaco?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "E10", label: "10. ¿Usa ropa ajustada?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" },
        { key: "E11", label: "11. ¿Practica deportes violentos?", desc: "0=Nada, nunca · 1=Poco, a veces · 2=Bastante, a menudo · 3=Mucho, siempre" }
      ]
    }
  ]
};

export const VHI10 = {
    name: 'Índice de Discapacidad Vocal (VHI-10 Oficial)',
    items: [
      { key: 'V1', label: '1. Mi voz me dificulta hacer que me escuchen en ambientes ruidosos', desc: '0=Nunca · 1=Casi nunca · 2=A veces · 3=Casi siempre · 4=Siempre' },
      { key: 'V2', label: '2. La gente tiene dificultad para oírme en ambientes ruidosos o concurridos', desc: '0=Nunca · 1=Casi nunca · 2=A veces · 3=Casi siempre · 4=Siempre' },
      { key: 'V3', label: '3. Mi voz me presenta problemas en mi trabajo o en mi vida personal', desc: '0=Nunca · 1=Casi nunca · 2=A veces · 3=Casi siempre · 4=Siempre' },
      { key: 'V4', label: '4. Me siento tenso al hablar', desc: '0=Nunca · 1=Casi nunca · 2=A veces · 3=Casi siempre · 4=Siempre' },
      { key: 'V5', label: '5. La calidad de mi voz es impredecible a lo largo del día', desc: '0=Nunca · 1=Casi nunca · 2=A veces · 3=Casi siempre · 4=Siempre' },
      { key: 'V6', label: '6. Mi voz "se corta" o me quedo sin aire cuando hablo', desc: '0=Nunca · 1=Casi nunca · 2=A veces · 3=Casi siempre · 4=Siempre' },
      { key: 'V7', label: '7. Siento que necesito esforzarme para producir mi voz', desc: '0=Nunca · 1=Casi nunca · 2=A veces · 3=Casi siempre · 4=Siempre' },
      { key: 'V8', label: '8. Mi voz suena ronca o áspera', desc: '0=Nunca · 1=Casi nunca · 2=A veces · 3=Casi siempre · 4=Siempre' },
      { key: 'V9', label: '9. Mi voz limita mi vida personal y social', desc: '0=Nunca · 1=Casi nunca · 2=A veces · 3=Casi siempre · 4=Siempre' },
      { key: 'V10', label: '10. Siento que la gente no comprende mi problema de voz', desc: '0=Nunca · 1=Casi nunca · 2=A veces · 3=Casi siempre · 4=Siempre' },
    ]
  };

/** Grupo de riesgo vocal según el puntaje total (misma regla que Riesgo & Escalas). */
export function grupoRiesgo(total: number): string {
  return total <= 69 ? 'Grupo 1 (Bajo Riesgo)' : total <= 138 ? 'Grupo 2 (Riesgo Moderado)' : 'Grupo 3 (Alto Riesgo)';
}
