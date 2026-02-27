# Code automatically generated - DO NOT EDIT.

import typing

import algopy as py
from algopy import logicsig, subroutine, BigUInt, Bytes, UInt64, urange
from algopy.arc4 import UInt256, DynamicArray
from algopy.op import bzero, sha256, EllipticCurve as ec, EC

#################### Curve parameters ####################

# curve order
R_MOD = 21888242871839275222246405745257275088548364400416034343698204186575808495617

# field order
P_MOD = 21888242871839275222246405745257275088696311157297823662689037894645226208583

#################### Trusted setup ####################

G2_SRS_0_X_0 = 11559732032986387107991004021392285783925812861821192530917403151452391805634
G2_SRS_0_X_1 = 10857046999023057135944570762232829481370756359578518086990519993285655852781
G2_SRS_0_Y_0 = 4082367875863433681332203403145435568316851327593401208105741076214120093531
G2_SRS_0_Y_1 = 8495653923123431417604973247489272438418190587263600148770280649306958101930

G2_SRS_1_X_0 = 19512854131067398948629626411628775647073463846025496268113693869795292473092
G2_SRS_1_X_1 = 21711638952687243716093869591886719008577686612740434959727952849032742141002
G2_SRS_1_Y_0 = 17367501458087994372613082725197650945890162654529042341165826675119905123507
G2_SRS_1_Y_1 = 16446673048952644848838269949246865620742974358211859963126899474188233428651

G1_SRS_X = 1
G1_SRS_Y = 2

######################################################

@logicsig(name="Verifier")
def verify() -> bool:
	"""Verify the proof for the given public inputs.
	   Fail if the proof is invalid"""

	q = BigUInt(R_MOD)

	# read proof and public inputs
	# they are passed in to an arc4 contract as DyanmicArray[Bytes32]
	# where Bytes32 is a 32 bytes StaticArray; so we skip the first 2 bytes which encode
	# the length of the array (we also skip the first app arg which is the method name)
	proof = py.Txn.application_args(1)[2:]
	public_inputs = py.Txn.application_args(2)[2:]

	# check proof and public inputs lengths
	assert proof.length == 24 * 32
	assert public_inputs.length == 6 * 32

	# Read verifying key
	VK_NB_PUBLIC_INPUTS = UInt64(6)
	VK_DOMAIN_SIZE = BigUInt(32768)
	VK_INV_DOMAIN_SIZE = BigUInt(21887574895677414892802367463831943750807625009412603678587617693528122466305)
	VK_OMEGA = BigUInt(20402931748843538985151001264530049874871572933694634836567070693966133783803)

	VK_QL = Bytes.from_hex("1e92b517f2f62e23e6c2a346697bf0df9be26cefa4f75a6d4962747f925571c7194e2ccf1498b51c352d24a9d750a1c56217a59387024bc571dd207370f96682")
	VK_QR = Bytes.from_hex("1a3a21273955d21fe35751642c0961c2a3f795269d2b49488a5ae29ebe2c80ea22034d1ec4a0320058a186eb7778c9e7a21381191bc305d07b42b80b92eb53b1")
	VK_QO = Bytes.from_hex("1929fb998a19285865b4d9fdce2f4838daa6c5db2883e275c3d7e917d5d054a91f3a4783d1db76103fc0a9cac46f74c923f7514a4d488e7a9164d43a7317f84f")
	VK_QM = Bytes.from_hex("0b24250a100bdde58f4b76ea2ea0bfee06d688f2370dc24393549212b1fa0cdd0e77dc580185211d61a499972d8ca022ca6d20cc2698ed3dfd2dd49fbf897da3")
	VK_QK = Bytes.from_hex("04937466b78cbf216e4ba0e0d3952b9cb09c5eed3e5164c5c1222aea121dbc8d0516f6c566f4a312332b9c22254c3fa9106589a494c787757de3d3ea0db60c3c")

	VK_S1 = Bytes.from_hex("2ba6c785c038431720e6672a78c9f6554484ce408b440422cb61268f425d238a00123fe05c65e5c6a3ba0d5dbbf7e552b8e766e439ed63a29d751b8c9446f14b")
	VK_S2 = Bytes.from_hex("0f00caf451cf5289280fea18b2cbf56f04f94def4c7e8e596d6303e23b886b2030095780ea39614ee019c61bcfe4ff856125ec51695d75eef198c6e9acbc5361")
	VK_S3 = Bytes.from_hex("1a05cbbf6f5d21de0106e246cdf2f413c05d0e3a39eb468a044fdb5af2c9925b07288546fed5c53220a69cdd6ef3dbe65f9fd5272bfa040a980ef3b5cec20129")
	
	VK_COSET_SHIFT = BigUInt(5)

	# Read proof #
	# wires commitments
	L_COM = proof[0:64]
	R_COM = proof[64:128]
	O_COM = proof[128:192]

	# h = h_0 + x^{n+2}h_1 + x^{2(n+2)}h_2
	H_0 = proof[192:256]
	H_1 = proof[256:320]
	H_2 = proof[320:384]

	# wire values at zeta
	L_AT_Z = proof[384:416]
	R_AT_Z = proof[416:448]
	O_AT_Z = proof[448:480]

	S1_AT_Z = proof[480:512]					# s1(zeta)
	S2_AT_Z = proof[512:544] 					# s2(zeta)
	GRAND_PRODUCT = proof[544:608]				# z(x)
	GRAND_PRODUCT_AT_Z_OMEGA = proof[608:640]   # z(w*zeta)

	# Folded proof for opening of linear poly, l, r, o, s1, s2
	BATCH_OPENING_AT_Z = proof[640:704]

	# opening at zeta * omega
	OPENING_AT_Z_OMEGA = proof[704:768]

	### check proof public inputs are well-formed ###
	if (BigUInt.from_bytes(L_AT_Z) >= q
			or BigUInt.from_bytes(R_AT_Z) >= q
			or BigUInt.from_bytes(O_AT_Z) >= q
			or BigUInt.from_bytes(S1_AT_Z) >= q
			or BigUInt.from_bytes(S2_AT_Z) >= q
			or BigUInt.from_bytes(GRAND_PRODUCT_AT_Z_OMEGA) >= q
	):
		return False

	for i in urange(VK_NB_PUBLIC_INPUTS):
		if BigUInt.from_bytes(public_inputs[i*32:(i+1)*32]) >= q:
			return False

	### Verify the proof ###

	# Compute the fiat-shamir challenges as the prover (gnark).
	# After deriving all challenges, we need to make them modulo R_MOD.

	gamma_pre = sha256(b'gamma' + VK_S1 + VK_S2 + VK_S3 + VK_QL + VK_QR
		+ VK_QM + VK_QO + VK_QK + public_inputs + L_COM + R_COM + O_COM)
	beta_pre = sha256(b'beta' + gamma_pre)
	alpha_pre = sha256(b'alpha' + beta_pre + GRAND_PRODUCT)
	zeta_pre = sha256(b'zeta' + alpha_pre + H_0 + H_1 + H_2)

	gamma = curvemod(gamma_pre)
	beta = curvemod(beta_pre)
	alpha = curvemod(alpha_pre)
	zeta = curvemod(zeta_pre)

	# Zz is eval of Xⁿ-1 at zeta
	Zz = (expmod(zeta, VK_DOMAIN_SIZE, q) + q - BigUInt(1)) % q

	# zn is Zz * 1/n
	zn = (Zz * VK_INV_DOMAIN_SIZE) % q

	# Let's prepare to interpolate the public inputs
	w_ = BigUInt(1)
	batch = DynamicArray[UInt256]()
	for i in urange(VK_NB_PUBLIC_INPUTS):
		x = (zeta + q - w_) % q
		batch.append(UInt256(x))
		w_ = (w_ * VK_OMEGA) % q

	# Compute batch inversion
	temp = DynamicArray[UInt256]()
	prev = BigUInt(1)
	temp.append(UInt256(prev))
	for x256 in batch:
		x = BigUInt.from_bytes(x256.bytes)
		y = (x * prev) % q
		temp.append(UInt256(y))
		prev = y
	inv = expmod(prev, q - BigUInt(2), q)
	i = VK_NB_PUBLIC_INPUTS
	while i > 0:
		tmp = BigUInt.from_bytes(batch[i-1].bytes)
		cur = (inv * BigUInt.from_bytes(temp[i-1].bytes)) % q
		batch[i-1] = UInt256(cur)
		inv = (inv * tmp) % q
		i -= 1

	# We can now interpolate the public inputs (PI)
	w_ = BigUInt(1)
	for i in urange(VK_NB_PUBLIC_INPUTS):
		batch[i] = UInt256((w_ * ((BigUInt.from_bytes(batch[i].bytes) * zn)
							% q)) % q)
		w_ = (w_ * VK_OMEGA) % q

	tmp = BigUInt(0)
	PI = BigUInt(0)
	for i in urange(VK_NB_PUBLIC_INPUTS):
		tmp = (BigUInt.from_bytes(batch[i].bytes)
				* BigUInt.from_bytes(public_inputs[i*32:(i+1)*32])) % q
		PI = (PI + tmp) % q

	# compute alpha2Lagrange: alpha**2 * (z**n - 1) / (z - 1)
	res = (zeta + q - BigUInt(1)) % q
	res = expmod(res, q - BigUInt(2), q)
	res = (res * zn) % q
	res = (res * alpha) % q
	res = (res * alpha) % q
	alpha2Lagrange = res

	# verify opening linearization polynomial
	s1 = (BigUInt.from_bytes(S1_AT_Z) * beta) % q
	s1 = (s1 + gamma + BigUInt.from_bytes(L_AT_Z)) % q

	s2 = (BigUInt.from_bytes(S2_AT_Z) * beta) % q
	s2 = (s2 + gamma + BigUInt.from_bytes(R_AT_Z)) % q

	o = (BigUInt.from_bytes(O_AT_Z) + gamma) % q

	s1 = (s1 * s2) % q
	s1 = (s1 * o) % q
	s1 = (s1 * alpha) % q
	s1 = (s1 * BigUInt.from_bytes(GRAND_PRODUCT_AT_Z_OMEGA)) % q

	s1 = (s1 + PI + q - alpha2Lagrange)  % q
	linearized_poly_at_z = (q - s1)

	# compute the folded commitment to H
	n2 = VK_DOMAIN_SIZE + BigUInt(2)
	zn2 = expmod(zeta, n2, q)
	folded_h = ec.scalar_mul(EC.BN254g1, H_2, zn2.bytes)
	folded_h = ec.add(EC.BN254g1, folded_h, H_1)
	folded_h = ec.scalar_mul(EC.BN254g1, folded_h, zn2.bytes)
	folded_h = ec.add(EC.BN254g1, folded_h, H_0)
	znminus1 = (expmod(zeta, VK_DOMAIN_SIZE, q) + q - BigUInt(1)) % q
	folded_h = ec.scalar_mul(EC.BN254g1, folded_h, znminus1.bytes)
	folded_h = invert(folded_h)

	# compute commitment to linearization polynomial
	u = (BigUInt.from_bytes(GRAND_PRODUCT_AT_Z_OMEGA) * beta) % q
	v = (BigUInt.from_bytes(S1_AT_Z) * beta) % q
	v = (v + BigUInt.from_bytes(L_AT_Z) + gamma) % q
	w  = (BigUInt.from_bytes(S2_AT_Z) * beta) % q
	w = (w + BigUInt.from_bytes(R_AT_Z) + gamma) % q

	s1 = (u * v) % q
	s1 = (s1 * w) % q
	s1 = (s1 * alpha) % q

	coset_square = (VK_COSET_SHIFT * VK_COSET_SHIFT) % q
	betazeta = (beta * zeta) % q
	u = (betazeta + BigUInt.from_bytes(L_AT_Z) + gamma) % q

	v = (betazeta * VK_COSET_SHIFT) % q
	v = (v + BigUInt.from_bytes(R_AT_Z) + gamma) % q

	w = (betazeta * coset_square) % q
	w = (w + BigUInt.from_bytes(O_AT_Z) + gamma) % q

	s2 = (u * v) % q
	s2 = q - ((s2 * w) % q)
	s2 = (s2 * alpha + alpha2Lagrange) % q

	lin_poly_com = ec.scalar_mul(EC.BN254g1, VK_QL, L_AT_Z)

	add_term = ec.scalar_mul(EC.BN254g1, VK_QR, R_AT_Z)
	lin_poly_com = ec.add(EC.BN254g1, lin_poly_com, add_term)

	add_term = ec.scalar_mul(EC.BN254g1, VK_QO, O_AT_Z)
	lin_poly_com = ec.add(EC.BN254g1, lin_poly_com, add_term)

	ab = (BigUInt.from_bytes(L_AT_Z) * BigUInt.from_bytes(R_AT_Z)) % q
	add_term = ec.scalar_mul(EC.BN254g1, VK_QM, ab.bytes)
	lin_poly_com = ec.add(EC.BN254g1, lin_poly_com, add_term)
	lin_poly_com = ec.add(EC.BN254g1, lin_poly_com, VK_QK)

	add_term = ec.scalar_mul(EC.BN254g1, VK_S3, s1.bytes)
	lin_poly_com = ec.add(EC.BN254g1, lin_poly_com, add_term)

	add_term = ec.scalar_mul(EC.BN254g1, GRAND_PRODUCT, s2.bytes)
	lin_poly_com = ec.add(EC.BN254g1, lin_poly_com, add_term)

	lin_poly_com = ec.add(EC.BN254g1, lin_poly_com, folded_h)

	# generate challenge to fold the opening proofs
	linearized_poly_at_z_bytes = bzero(32) | linearized_poly_at_z.bytes
	r_pre = sha256(b'gamma' + UInt256(zeta).bytes + lin_poly_com
		 + L_COM + R_COM + O_COM + VK_S1 + VK_S2 + linearized_poly_at_z_bytes
		 + L_AT_Z + R_AT_Z + O_AT_Z + S1_AT_Z
		 + S2_AT_Z + GRAND_PRODUCT_AT_Z_OMEGA)
	r = curvemod(r_pre)
	r_acc = r

	# fold the proof in one point
	digest = lin_poly_com
	claims = linearized_poly_at_z

	add_term = ec.scalar_mul(EC.BN254g1, L_COM, r_acc.bytes)
	digest = ec.add(EC.BN254g1, digest, add_term)
	claims = (claims + (BigUInt.from_bytes(L_AT_Z) * r_acc)) % q

	r_acc = (r_acc * r) % q
	add_term = ec.scalar_mul(EC.BN254g1, R_COM, r_acc.bytes)
	digest = ec.add(EC.BN254g1, digest, add_term)
	claims = (claims + (BigUInt.from_bytes(R_AT_Z) * r_acc)) % q

	r_acc = (r_acc * r) % q
	add_term = ec.scalar_mul(EC.BN254g1, O_COM, r_acc.bytes)
	digest = ec.add(EC.BN254g1, digest, add_term)
	claims = (claims + (BigUInt.from_bytes(O_AT_Z) * r_acc)) % q

	r_acc = (r_acc * r) % q
	add_term = ec.scalar_mul(EC.BN254g1, VK_S1, r_acc.bytes)
	digest = ec.add(EC.BN254g1, digest, add_term)
	claims = (claims + (BigUInt.from_bytes(S1_AT_Z) * r_acc)) % q

	r_acc = (r_acc * r) % q
	add_term = ec.scalar_mul(EC.BN254g1, VK_S2, r_acc.bytes)
	digest = ec.add(EC.BN254g1, digest, add_term)
	claims = (claims + (BigUInt.from_bytes(S2_AT_Z) * r_acc)) % q

	# verify the folded proof
	r_pre = sha256(digest + BATCH_OPENING_AT_Z + GRAND_PRODUCT + OPENING_AT_Z_OMEGA + UInt256(zeta).bytes + UInt256(r).bytes)
	r = curvemod(r_pre)

	quotient = BATCH_OPENING_AT_Z
	add_term = ec.scalar_mul(EC.BN254g1, OPENING_AT_Z_OMEGA, r.bytes)
	quotient = ec.add(EC.BN254g1, quotient, add_term)

	add_term = ec.scalar_mul(EC.BN254g1, GRAND_PRODUCT, r.bytes)
	digest = ec.add(EC.BN254g1, digest, add_term)

	claims = (claims + (BigUInt.from_bytes(GRAND_PRODUCT_AT_Z_OMEGA)
			  * r)) % q
	G1_SRS = UInt256(G1_SRS_X).bytes + UInt256(G1_SRS_Y).bytes
	claims_com = ec.scalar_mul(EC.BN254g1, G1_SRS, claims.bytes)

	digest = ec.add(EC.BN254g1, digest, invert(claims_com))

	points_quotient = ec.scalar_mul(EC.BN254g1, BATCH_OPENING_AT_Z, zeta.bytes)

	zeta_omega = (zeta * VK_OMEGA) % q
	r = (r * zeta_omega) % q
	add_term = ec.scalar_mul(EC.BN254g1, OPENING_AT_Z_OMEGA, r.bytes)
	points_quotient = ec.add(EC.BN254g1, points_quotient, add_term)

	digest = ec.add(EC.BN254g1, digest, points_quotient)
	quotient = invert(quotient)

	g2 = (UInt256(G2_SRS_0_X_1).bytes + UInt256(G2_SRS_0_X_0).bytes
	   + UInt256(G2_SRS_0_Y_1).bytes + UInt256(G2_SRS_0_Y_0).bytes
	   + UInt256(G2_SRS_1_X_1).bytes + UInt256(G2_SRS_1_X_0).bytes
	   + UInt256(G2_SRS_1_Y_1).bytes + UInt256(G2_SRS_1_Y_0).bytes)

	check = ec.pairing_check(EC.BN254g1, digest + quotient, g2)
	return check



@subroutine
def expmod(base: BigUInt, exponent: BigUInt, modulus: BigUInt) -> BigUInt:
	"""Compute base^exponent % modulus."""
	result = BigUInt(1)
	while exponent > 0:
		if exponent % 2 == 1:
			result = (result * base) % modulus
		exponent = exponent // 2
		base = (base * base) % modulus
	return result

@subroutine
def curvemod(x: Bytes) -> BigUInt:
	"""Compute x % R_MOD."""
	return BigUInt.from_bytes(x) % BigUInt(R_MOD)

@subroutine
def invert(p : Bytes) -> Bytes:
	"""Invert a point on the curve."""
	x = BigUInt.from_bytes(p[:32])
	y = BigUInt.from_bytes(p[32:])
	neg_y = BigUInt(P_MOD) - y
	return x.bytes + UInt256(neg_y).bytes
