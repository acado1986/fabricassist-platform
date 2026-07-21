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
    scanTitle: 'Sube una etiqueta de cuidado',
    scanDescription:
      'Añade una foto clara para que FabricAssist prepare una consulta segura.',
    scanStep: 'FOTO DE LA ETIQUETA',
    required: 'Obligatoria',
    chooseImage: 'Elegir imagen de la etiqueta',
    changeImage: 'Elegir otra imagen',
    imageGuidance: 'Incluye toda la etiqueta y evita reflejos o desenfoques.',
    imageFormats: 'JPEG, PNG o WebP · Máximo 12 MB',
    selectedImage: 'Imagen seleccionada de la etiqueta',
    uploadImage: 'Subir imagen de forma segura',
    uploadingImage: 'Subiendo de forma segura…',
    scanComplete:
      'Carga completada. El análisis estará disponible en una fase posterior.',
    scanCreateFailed: 'No hemos podido preparar la carga. Inténtalo de nuevo.',
    scanUploadFailed:
      'La carga ha fallado. Revisa tu conexión e inténtalo de nuevo.',
    scanValidationFailed:
      'No hemos podido validar la imagen. Haz otra foto clara y bien iluminada.',
    signOut: 'Cerrar sesión',
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
