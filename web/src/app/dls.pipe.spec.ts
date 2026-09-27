import { DlsPipe, parseDls } from './dls.pipe';

describe('DlsPipe', () => {
  const pipe = new DlsPipe();

  it('formats parts zero-padded with the meridian suffix', () => {
    expect(pipe.transform({ lsd: 4, section: 10, township: 85, range: 17, meridian: 5 })).toBe('04-10-085-17 W5M');
  });

  it('parses the raw ST1 string and normalises it', () => {
    expect(pipe.transform('13-26-061-16W4')).toBe('13-26-061-16 W4M');
    expect(parseDls('4-10-85-17 W5M')).toEqual({ lsd: 4, section: 10, township: 85, range: 17, meridian: 5 });
  });

  it('passes unparseable strings through and blanks null', () => {
    expect(pipe.transform('n/a')).toBe('n/a');
    expect(pipe.transform(null)).toBe('');
    expect(parseDls('garbage')).toBeNull();
  });
});
