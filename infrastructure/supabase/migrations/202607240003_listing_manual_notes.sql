alter table deal_scanner.listings
  add column if not exists manual_note text;

alter table deal_scanner.listings
  drop constraint if exists listings_manual_note_length;

alter table deal_scanner.listings
  add constraint listings_manual_note_length
  check (manual_note is null or char_length(manual_note) <= 10000);
