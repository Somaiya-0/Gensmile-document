import { z } from "zod"

const phonePattern = /^[+\d().\-\s]{7,20}$/

const trimmedString = (label: string, minLength = 1, maxLength = 255) =>
  z
    .string()
    .trim()
    .min(minLength, `${label} is required.`)
    .max(maxLength, `${label} is too long.`)

const emailSchema = z
  .string()
  .trim()
  .min(1, "Email address is required.")
  .email("Enter a valid email address.")

const phoneSchema = z
  .string()
  .trim()
  .min(1, "Phone number is required.")
  .regex(phonePattern, "Enter a valid phone number.")

const passwordSchema = z
  .string()
  .min(8, "Password must be at least 8 characters.")
  .max(128, "Password must be 128 characters or less.")

const loginSchema = z.object({
  email: emailSchema,
  password: z
    .string()
    .min(8, "Password must be at least 8 characters.")
    .max(128, "Password must be 128 characters or less."),
})

const forgotPasswordSchema = z.object({
  email: emailSchema,
})

const accountSchema = z
  .object({
    acceptTerms: z.boolean(),
    confirmPassword: z.string(),
    email: emailSchema,
    fullName: trimmedString("Full name", 2),
    password: passwordSchema,
    referralCode: z
      .string()
      .trim()
      .max(64, "Referral code is too long.")
      .optional(),
  })
  .superRefine((value, context) => {
    if (value.password !== value.confirmPassword) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Passwords do not match.",
        path: ["confirmPassword"],
      })
    }

    if (!value.acceptTerms) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "You must accept the terms to continue.",
        path: ["acceptTerms"],
      })
    }
  })

const planSelectionSchema = z.object({
  selectedPlanCode: z.enum(["starter", "professional", "custom"], {
    message: "Select a plan to continue.",
  }),
})

const clinicSchema = z.object({
  address: trimmedString("Clinic address", 5, 1000),
  clinicName: trimmedString("Clinic name", 2),
  logoName: z.string().trim().max(255, "Logo file name is too long.").optional(),
  phone: phoneSchema,
})

const staffMemberSchema = z.object({
  email: emailSchema,
  fullName: trimmedString("Staff name", 2),
  role: trimmedString("Staff role", 2, 100),
})

const doctorDetailsSchema = z
  .object({
    clinics: z.array(clinicSchema).min(1, "At least one clinic is required."),
    staffMembers: z.array(staffMemberSchema),
  })
  .superRefine((value, context) => {
    const emails = value.staffMembers.map((member) => member.email.toLowerCase())
    const duplicateEmail = emails.find(
      (email, index) => emails.indexOf(email) !== index
    )

    if (!duplicateEmail) {
      return
    }

    value.staffMembers.forEach((member, index) => {
      if (member.email.toLowerCase() === duplicateEmail) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Staff email addresses must be unique.",
          path: ["staffMembers", index, "email"],
        })
      }
    })
  })

const patientDetailsSchema = z.object({
  birthDate: z
    .string()
    .trim()
    .optional()
    .refine((value) => !value || !Number.isNaN(Date.parse(value)), {
      message: "Enter a valid birth date.",
    })
    .refine((value) => !value || new Date(value) <= new Date(), {
      message: "Birth date cannot be in the future.",
    }),
  bloodGroup: z.string().trim().optional(),
  city: trimmedString("City", 2, 120),
  countryCode: z
    .string()
    .trim()
    .min(2, "Select a country.")
    .max(10, "Country code is too long."),
  countryName: trimmedString("Country", 2, 120),
  email: emailSchema,
  fullAddress: trimmedString("Full address", 5, 1000),
  fullName: trimmedString("Full name", 2),
  gender: z.string().trim().optional(),
  phone: phoneSchema,
  preferredContactMethod: z.enum(["sms", "email", "phone"]),
  stateCode: z.string().trim().optional(),
  stateName: trimmedString("State", 2, 120),
  streetAddress: trimmedString("Street address", 2, 255),
  zipCode: trimmedString("Zip code", 2, 30),
})

const resetPasswordSchema = z
  .object({
    confirmPassword: z.string(),
    password: z.string().min(1, "Password is required."),
    token: z
      .string()
      .trim()
      .min(32, "Your password reset link is incomplete or invalid.")
      .max(512, "Your password reset link is invalid."),
  })
  .superRefine((value, context) => {
    if (value.password !== value.confirmPassword) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Passwords do not match.",
        path: ["confirmPassword"],
      })
    }
  })

function getFieldErrors(error: z.ZodError) {
  const flattenedErrors = error.flatten().fieldErrors

  return Object.entries(flattenedErrors).reduce<Record<string, string>>(
    (result, [key, value]) => {
      if (Array.isArray(value) && value.length > 0) {
        result[key] = value[0] ?? "Invalid value."
      }

      return result
    },
    {}
  )
}

export {
  accountSchema,
  clinicSchema,
  doctorDetailsSchema,
  emailSchema,
  forgotPasswordSchema,
  getFieldErrors,
  loginSchema,
  patientDetailsSchema,
  phoneSchema,
  planSelectionSchema,
  resetPasswordSchema,
  staffMemberSchema,
}
