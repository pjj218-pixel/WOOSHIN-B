(function (root) {
  const lincoln409 = 'https://ch-delivery.lincolnelectric.com/api/public/content/f5e38ae6ebf441829d73d7b1a404818b?v=84bee2da';
  const lincolnStainless = 'https://ch-delivery.lincolnelectric.com/api/public/content/468b884c48d34770b842ed4d20610306?v=edd177d4';
  const esabDissimilar = 'https://esab.com/ae/mea_en/esab-university/blogs/welding-dissimilar-metals-using-309-stainless-steel/';

  function recommendWire(row, process, equipment, gas) {
    const complete = row.materialA && row.materialB && row.thicknessA > 0 && row.thicknessB > 0 && row.joint && row.position && process && equipment.trim() && gas;
    if (!complete) return { status: 'insufficient', message: '재질·두께·이음 형상·자세·용접 방식·설비·보호가스를 모두 입력해야 후보를 검토할 수 있습니다.' };
    if (process !== 'GMAW') return { status: 'insufficient', message: '현재 와이어 후보 규칙은 MIG/MAG(GMAW)만 지원합니다.' };

    const materials = [row.materialA, row.materialB].sort();
    const both409 = materials.every(material => material === '409' || material === '409Ti');
    const both304L = materials.every(material => material === '304L');
    const both304 = materials.every(material => material === '304');
    const carbonStainless = materials.includes('carbon') && materials.some(material => material === '304' || material === '304L');

    if (both409) return {
      status: 'candidate', wire: 'ER409Nb',
      reason: '제조사가 409·409Ti 모재와 자동차 배기계에 적용하도록 제시한 페라이트계 와이어입니다.',
      gasNote: gas === 'Ar98O2_2' ? '입력한 가스가 인용 제품 자료의 Ar 98% / O₂ 2%와 일치합니다.' : '입력한 보호가스가 인용 제품의 제시값과 다릅니다. 해당 가스 조합의 적합성을 먼저 확인하세요.',
      sourceLabel: 'Lincoln Electric ER409Nb 제품 자료', sourceUrl: lincoln409
    };
    if (both304L) return {
      status: 'candidate', wire: 'ER308L 또는 ER308LSi',
      reason: '제조사의 304L 모재용 GMAW 용가재 표에 제시된 분류입니다.',
      gasNote: '선택한 제품과 보호가스의 조합은 해당 제품 자료 및 장비 조건으로 별도 확인해야 합니다.',
      sourceLabel: 'Lincoln Electric 스테인리스 용가재 표', sourceUrl: lincolnStainless
    };
    if (both304) return {
      status: 'candidate', wire: 'ER308 또는 ER308Si',
      reason: '제조사의 304 모재용 GMAW 용가재 표에 제시된 분류입니다.',
      gasNote: '선택한 제품과 보호가스의 조합은 해당 제품 자료 및 장비 조건으로 별도 확인해야 합니다.',
      sourceLabel: 'Lincoln Electric 스테인리스 용가재 표', sourceUrl: lincolnStainless
    };
    if (carbonStainless) return {
      status: 'candidate', wire: 'ER309LSi',
      reason: '탄소강과 스테인리스 이종재를 GMAW로 접합한 제조사 사례의 와이어입니다. 이 부품에 대한 적합성은 별도 시험이 필요합니다.',
      gasNote: gas === 'Ar98CO2_2' ? '입력한 가스가 인용 사례의 Ar 98% / CO₂ 2%와 일치합니다.' : '입력한 보호가스가 인용 사례와 다릅니다. 해당 가스 조합의 적합성을 먼저 확인하세요.',
      sourceLabel: 'ESAB 이종재 GMAW 사례', sourceUrl: esabDissimilar
    };
    return { status: 'insufficient', message: '이 재질 조합의 검증된 후보 규칙이 없습니다. 제조사 자료와 사내 WPS를 확인해야 합니다.' };
  }

  const api = { recommendWire };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.WeldWire = api;
})(globalThis);
