import type { TranslationCatalog } from './types';

export const es: TranslationCatalog = {
  shell: {
    title: 'FabricAssist',
    foundation: 'Base de desarrollo',
    tagline: 'Cuidado de prendas basado en evidencias',
    privacyNote:
      'Tus imágenes son privadas y solo se usan para preparar tu consulta de cuidado.',
    loginTitle: 'Te damos la bienvenida',
    loginDescription:
      'Inicia sesión para subir una etiqueta y mantener juntas tus consultas.',
    registerTitle: 'Crea tu cuenta',
    registerDescription:
      'Empieza con una foto clara de la etiqueta. Solo necesitas un minuto.',
    emailLabel: 'Correo electrónico',
    emailPlaceholder: 'tu@ejemplo.com',
    emailError: 'Introduce un correo electrónico válido.',
    passwordLabel: 'Contraseña',
    passwordPlaceholder: 'Al menos 12 caracteres',
    passwordHint: 'Usa 12 caracteres o más.',
    passwordError: 'La contraseña debe tener al menos 12 caracteres.',
    loginAction: 'Iniciar sesión',
    registerAction: 'Crear cuenta',
    loginError:
      'No hemos podido iniciar sesión. Revisa tus datos e inténtalo de nuevo.',
    registerError:
      'No hemos podido crear la cuenta. Es posible que el correo ya esté registrado.',
    needAccount: '¿Eres nuevo en FabricAssist?',
    haveAccount: '¿Ya tienes una cuenta?',
    scanTitle: 'Añade una foto de la prenda o de la etiqueta',
    scanDescription:
      'Elige cualquiera de las dos. Incluye ambas si las tienes para aportar más contexto.',
    careLabelPhoto: 'FOTO DE LA ETIQUETA',
    garmentPhoto: 'FOTO DE LA PRENDA',
    takePhoto: 'Hacer foto',
    uploadExistingImage: 'Subir una imagen',
    cameraTitle: 'Hacer una foto',
    cameraDescription: 'Coloca la prenda o la etiqueta dentro del encuadre.',
    cameraCapture: 'Capturar foto',
    cameraCancel: 'Cancelar',
    chooseGarmentImage: 'Añade una vista general de la prenda',
    changeGarmentImage: 'Foto de la prenda seleccionada',
    garmentImageGuidance:
      'Muestra la prenda completa, su forma y los detalles visibles.',
    selectedGarmentImage: 'Imagen seleccionada de la prenda',
    chooseCareLabelImage: 'Añade un primer plano de la etiqueta',
    changeCareLabelImage: 'Foto de la etiqueta seleccionada',
    careLabelImageGuidance:
      'Incluye todo el texto y los símbolos sin reflejos ni desenfoques.',
    selectedCareLabelImage: 'Imagen seleccionada de la etiqueta',
    required: 'Opción de foto',
    imageFormats: 'JPEG, PNG o WebP · Máximo 12 MB',
    uploadImages: 'Analizar etiqueta de cuidado',
    uploadingImages: 'Subiendo de forma segura…',
    cameraPermissionFailed:
      'Se necesita acceso a la cámara para hacer una foto. También puedes subir una imagen.',
    scanComplete:
      'Carga completada. Estamos preparando el análisis de la etiqueta…',
    analysisQueued: 'Estamos analizando la(s) foto(s) seleccionada(s).',
    analysisFailed:
      'No pudimos analizar la imagen. Prueba con una foto más clara.',
    analysisProviderFailed:
      'El servicio de análisis no pudo completar esta solicitud. Inténtalo de nuevo en unos instantes.',
    viewResult: 'Ver instrucciones de cuidado',
    scanCreateFailed: 'No hemos podido preparar la carga. Inténtalo de nuevo.',
    scanUploadFailed:
      'La carga ha fallado. Revisa tu conexión e inténtalo de nuevo.',
    scanValidationFailed:
      'No hemos podido validar la imagen. Haz otra foto clara y bien iluminada.',
    signOut: 'Cerrar sesión',
    resultTitle: 'Tus instrucciones de cuidado',
    resultDescription:
      'Estas indicaciones se basan en la evidencia que pudimos verificar en la etiqueta.',
    resultLoading: 'Preparando tus instrucciones de cuidado…',
    resultUnavailable: 'Tus instrucciones de cuidado aún no están listas.',
    resultActions: 'Cuidado recomendado',
    resultProhibitions: 'No hagas esto',
    resultProfessional: 'Cuidado profesional',
    resultUncertainties: 'Lo que no pudimos confirmar',
    resultDetergent: 'Orientación sobre detergente',
    backToScan: 'Analizar otra etiqueta',
    status: 'Todavía no hay funcionalidad de negocio disponible.',
    language: 'Idioma',
    languageEnglish: 'Inglés',
    languageSpanish: 'Español',
    diagnostics: 'Diagnóstico de salud',
    diagnosticsDescription:
      'Comprueba el endpoint de salud de la API solo durante el desarrollo.',
    checkHealth: 'Comprobar salud de la API',
    healthReady: 'La salud de la API está disponible.',
    healthUnavailable: 'La salud de la API no está disponible.',
    notFoundTitle: 'Página no encontrada',
    notFoundDescription: 'Esta ruta no forma parte de la base de la fase 3.',
    goHome: 'Ir al inicio de la base',
  },
};
