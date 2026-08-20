import { RelayPool } from "applesauce-relay";
import { ExtensionSigner, NostrConnectSigner } from "applesauce-signers";

/**
 * Owner signing via applesauce. The owner key signs the admin events
 * that claim and control the totem (NIP-98-style, spec 06/10).
 */

// NIP-46 signers talk through relays; one shared pool for the app.
NostrConnectSigner.pool = new RelayPool();

export interface OwnerSigner {
  getPublicKey(): Promise<string>;
  signEvent(template: {
    kind: number;
    created_at: number;
    tags: string[][];
    content: string;
  }): Promise<unknown>;
}

/** The claim event the owner signs (kind 27235, NIP-98 shape). */
function claimTemplate() {
  return {
    kind: 27235,
    created_at: Math.floor(Date.now() / 1000),
    tags: [
      ["u", "http://totem.local:8080/totem/claim"],
      ["method", "POST"],
    ],
    content: "",
  };
}

/** Connect a NIP-07 browser extension and sign the claim. */
export async function claimWithExtension(): Promise<{ pubkey: string; signer: OwnerSigner }> {
  const signer = new ExtensionSigner();
  const pubkey = await signer.getPublicKey();
  await signer.signEvent(claimTemplate());
  return { pubkey, signer };
}

/** Connect a NIP-46 remote signer from a bunker:// URI and sign the claim. */
export async function claimWithBunker(uri: string): Promise<{ pubkey: string; signer: OwnerSigner }> {
  const signer = await NostrConnectSigner.fromBunkerURI(uri, {
    permissions: NostrConnectSigner.buildSigningPermissions([27235]),
  });
  const pubkey = await signer.getPublicKey();
  await signer.signEvent(claimTemplate());
  return { pubkey, signer };
}
